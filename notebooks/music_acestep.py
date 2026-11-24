"""Generate and resume ACE-Step score candidates in a CUDA notebook."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter


def input_digest(value):
    # Match pipeline.utils.input_hash for inputs with no attached files.
    payload = {"inputs": value, "file_hashes": []}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def generate(manifest, output, ace_root):
    bundle = json.loads(manifest.read_text(encoding="utf-8"))
    caption = bundle["caption"]
    output.mkdir(parents=True, exist_ok=True)
    handler = None
    current_model = None
    for candidate in bundle["candidates"]:
        digest = candidate["input_hash"]
        contract = {key: value for key, value in candidate.items() if key != "input_hash"}
        if digest != input_digest(contract) or candidate["caption_hash"] != input_digest(caption):
            raise ValueError("Music inputs do not match the manifest")
        option = candidate["candidate"]
        track = output / f"{option}_{digest}.wav"
        sidecar = track.with_suffix(".json")
        if track.is_file() and sidecar.is_file():
            previous = json.loads(sidecar.read_text(encoding="utf-8"))
            if (all(previous.get(key) == value for key, value in candidate.items())
                    and previous.get("output_sha256") == file_digest(track)
                    and all(previous.get(name) is not None for name in ("latency_s", "gpu_minutes"))):
                print(f"Candidate {option}: existing track")
                continue

        from acestep.handler import AceStepHandler
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        if current_model != candidate["model"]:
            handler = AceStepHandler()
            status, success = handler.initialize_service(
                project_root=str(ace_root), config_path=candidate["model"],
                device="cuda", use_flash_attention=False, offload_to_cpu=True,
            )
            if not success:
                raise RuntimeError(f"ACE-Step initialization failed: {status}")
            current_model = candidate["model"]
        settings = candidate["params"]
        seed = candidate["seed"]
        params = GenerationParams(
            task_type="text2music", caption=caption, lyrics="[Instrumental]",
            instrumental=settings["instrumental"], bpm=settings["bpm"],
            duration=settings["duration_s"], inference_steps=settings["inference_steps"],
            seed=seed, thinking=False, use_cot_caption=False,
            use_cot_metas=False, use_cot_language=False,
        )
        config = GenerationConfig(batch_size=1, seeds=[seed], use_random_seed=False, audio_format="wav")
        with TemporaryDirectory(dir=output) as temporary:
            started = perf_counter()
            result = generate_music(handler, None, params, config, save_dir=temporary)
            elapsed = perf_counter() - started
            if not result.success or len(result.audios) != 1:
                raise RuntimeError(f"Candidate {option} failed: {result.error}")
            Path(result.audios[0]["path"]).replace(track)
        metadata = {**candidate, "output_sha256": file_digest(track),
                    "latency_s": elapsed, "gpu_minutes": elapsed / 60}
        pending = sidecar.with_suffix(".partial")
        pending.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        pending.replace(sidecar)
        print(f"Candidate {option}: saved {track}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ace-root", type=Path, default=Path.cwd(),
                        help="ACE-Step installation directory")
    args = parser.parse_args()
    generate(args.manifest, args.output, args.ace_root.resolve())


if __name__ == "__main__":
    main()
