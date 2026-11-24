"""Run a prepared Wan bundle on a Kaggle CUDA GPU."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter


def input_digest(value):
    # Match pipeline.utils.input_hash for inputs with no attached files.
    payload = {"inputs": value, "file_hashes": []}
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def file_digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_pipeline(model, device):
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline

    if not torch.cuda.is_available() or not 0 <= device < torch.cuda.device_count():
        raise RuntimeError(f"CUDA device {device} is unavailable")
    with torch.cuda.device(device):
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
    vae = AutoencoderKLWan.from_pretrained(model, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(model, vae=vae, torch_dtype=dtype)
    pipe.enable_model_cpu_offload(gpu_id=device)
    pipe.vae.enable_tiling()
    return pipe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--shot", type=int, action="append", help="Repeat to select several shots")
    parser.add_argument("--device", type=int, default=0, help="CUDA device index")
    args = parser.parse_args()
    storyboard = json.loads((args.bundle / "storyboard.json").read_text(encoding="utf-8"))
    shots = {shot["id"]: shot for shot in storyboard["shots"]}
    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    selected = [entry for entry in manifest if args.shot is None or entry["shot_id"] in args.shot]
    if args.shot and set(args.shot) != {entry["shot_id"] for entry in selected}:
        parser.error("A requested shot is missing from the bundle")
    args.output.mkdir(parents=True, exist_ok=True)
    pipe = None
    current_model = None
    for entry in selected:
        contract = {key: value for key, value in entry.items() if key != "keyframe"}
        identifier = entry["shot_id"]
        keyframe = args.bundle / entry["keyframe"]
        motion = shots[identifier]["motion_prompt"]
        contract_inputs = {key: value for key, value in contract.items() if key != "input_hash"}
        if (input_digest(contract_inputs) != contract["input_hash"]
                or input_digest(motion) != contract["motion_sha256"]
                or file_digest(keyframe) != contract["keyframe_sha256"]):
            raise ValueError(f"Shot {identifier} inputs do not match the manifest")
        stem = f"{identifier}_{entry['input_hash']}"
        clip = args.output / f"{stem}.mp4"
        sidecar = clip.with_suffix(".json")
        if clip.is_file() and sidecar.is_file():
            previous = json.loads(sidecar.read_text(encoding="utf-8"))
            if previous == {**contract, "output_sha256": file_digest(clip),
                            "latency_s": previous.get("latency_s"), "gpu_minutes": previous.get("gpu_minutes")}:
                print(f"Shot {identifier}: existing clip")
                continue

        import torch
        from diffusers.utils import export_to_video
        from PIL import Image, ImageOps

        if current_model != entry["model"]:
            pipe = load_pipeline(entry["model"], args.device)
            current_model = entry["model"]
        params = dict(entry["params"])
        fps = params.pop("fps")
        with Image.open(keyframe) as source:
            image = ImageOps.fit(source.convert("RGB"), (params["width"], params["height"]),
                                 method=Image.Resampling.LANCZOS)
        started = perf_counter()
        frames = pipe(prompt=motion, image=image, generator=torch.Generator().manual_seed(entry["seed"]),
                      **params).frames[0]
        elapsed = perf_counter() - started
        temporary = args.output / f"{stem}.partial.mp4"
        export_to_video(frames, str(temporary), fps=fps, macro_block_size=1)
        temporary.replace(clip)
        metadata = {**contract, "output_sha256": file_digest(clip), "latency_s": elapsed,
                    "gpu_minutes": elapsed / 60}
        pending = sidecar.with_suffix(".partial")
        pending.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        pending.replace(sidecar)
        print(f"Shot {identifier}: saved {clip}", flush=True)


if __name__ == "__main__":
    main()
