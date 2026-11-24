"""Render local motion clips or reuse matching imported Wan clips."""

import argparse
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import yaml

from pipeline.keyframes import Keyframes
from pipeline.narration import load_project
from pipeline.utils import CacheIndex, canonical_json, file_hash, input_hash, write_artifact
from pipeline.validate import ROOT


def wan_contract(config, shot, keyframe, quality):
    provider = config["providers"]["shots"]
    height = provider[f"{quality}_height"]
    values = {
        "model": provider["model"], "shot_id": shot["id"], "quality": quality,
        "keyframe_sha256": file_hash(keyframe), "seed": shot["seed"],
        "motion_sha256": input_hash(shot["motion_prompt"]),
        "params": {
            "width": height, "height": height, "fps": config["assembly"]["fps"],
            **{name: provider[name] for name in ("num_frames", "num_inference_steps", "guidance_scale")},
        },
    }
    return {**values, "input_hash": input_hash(values)}


def shot_inputs(root, config, storyboard, shot_id=None):
    frames = Keyframes(root, config, storyboard).generate(shot_id, cached_only=True)
    shots = [shot for shot in storyboard["shots"] if shot_id is None or shot["id"] == shot_id]
    return list(zip(shots, frames, strict=True))


def export_wan_bundle(directory, config, storyboard, pairs, quality):
    entries = []
    for shot, keyframe in pairs:
        contract = wan_contract(config, shot, keyframe, quality)
        relative = f"keyframes/{keyframe.name}"
        write_artifact(directory / relative, keyframe.read_bytes())
        entries.append({**contract, "keyframe": relative})
    selected_shots = [shot for shot, _ in pairs]
    write_artifact(directory / "storyboard.json",
                   (canonical_json({**storyboard, "shots": selected_shots}) + "\n").encode("utf-8"))
    write_artifact(directory / "manifest.json", (canonical_json(entries) + "\n").encode("utf-8"))


def motion_filter(shot, size, frames, fps, zoom):
    motion = shot["motion_prompt"].lower()
    t = f"on/{max(frames - 1, 1)}"
    x, y = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    z = f"1+{zoom}*{t}"
    if "pull-out" in motion or "zoom out" in motion:
        z = f"1+{zoom}*(1-{t})"
    elif "pan" in motion or "drift" in motion:
        z = f"1+{zoom}"
        x = f"(iw-iw/zoom)*(0.2+0.6*{t})"
    elif "tilt" in motion:
        z = f"1+{zoom}"
        y = f"(ih-ih/zoom)*(0.8-0.6*{t})"
    elif "locked off" in motion:
        z = "1"
    return (
        f"scale={size * 2}:{size * 2}:force_original_aspect_ratio=increase,"
        f"crop={size * 2}:{size * 2},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={size}x{size}:fps={fps},"
        "setsar=1,format=yuv420p"
    )


def generate_shots(root, config, pairs, *, ffmpeg="ffmpeg"):
    cache = CacheIndex(root / config["paths"]["cache_index"])
    outputs = root / config["paths"]["outputs"] / "shots"
    fps = config["assembly"]["fps"]
    codec = config["assembly"]["video_codec"]
    size = config["shots"]["fallback_size"]
    zoom = config["shots"]["fallback_zoom"]
    paths = []
    for shot, keyframe in pairs:
        shot_id = shot["id"]
        imported = None
        for quality in ("final", "draft"):
            contract = wan_contract(config, shot, keyframe, quality)
            imported = cache.lookup("wan", shot_id, contract["input_hash"])
            if imported is not None:
                break
        if imported is not None:
            print(f"Shot {shot_id}: Wan ({quality})")
            paths.append(imported)
            continue
        frames = max(1, math.ceil(shot["duration_s"] * fps))
        filters = motion_filter(shot, size, frames, fps, zoom)
        digest = input_hash({"filter": filters, "codec": codec, "frames": frames, "version": 2}, files=[keyframe])
        output = cache.lookup("shots", shot_id, digest)
        if output is None:
            output = outputs / f"{shot_id}_{digest}.mp4"
            outputs.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=outputs) as directory:
                temporary = Path(directory) / "clip.mp4"
                subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(keyframe),
                     "-vf", filters, "-frames:v", str(frames), "-an",
                     "-c:v", codec, "-movflags", "+faststart", str(temporary)],
                    check=True,
                )
                write_artifact(output, temporary)
            cache.record("shots", shot_id, digest, output)
        print(f"Shot {shot_id}: Ken Burns")
        paths.append(output)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", type=int)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--export-wan", type=Path, metavar="DIRECTORY")
    parser.add_argument("--quality", choices=("draft", "final"), default="draft")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(ROOT)
        pairs = shot_inputs(ROOT, config, storyboard, args.shot)
        if args.export_wan is not None:
            export_wan_bundle(args.export_wan, config, storyboard, pairs, args.quality)
            print(f"Wan inputs ready at {args.export_wan}")
        else:
            generate_shots(ROOT, config, pairs, ffmpeg=args.ffmpeg)
    except (OSError, ValueError, KeyError, yaml.YAMLError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
