"""Import verified Wan or ACE-Step outputs for the current storyboard."""

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess

import yaml

from pipeline.narration import load_project
from pipeline.music import import_music
from pipeline.shots import shot_inputs, wan_contract
from pipeline.utils import CacheIndex, file_hash, log_run, write_artifact
from pipeline.validate import add_workdir_argument


def check_clip(path, params, ffprobe):
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    if not streams:
        raise ValueError(f"{path.name} has no video stream")
    stream = streams[0]
    if (stream["width"], stream["height"], Fraction(stream["avg_frame_rate"]),
            int(stream["nb_read_frames"])) != (
            params["width"], params["height"], params["fps"], params["num_frames"]):
        raise ValueError(f"{path.name} does not match the sidecar video settings")


def import_wan(root, config, pairs, directory, *, ffprobe="ffprobe"):
    expected = {}
    for shot, keyframe in pairs:
        for quality in ("draft", "final"):
            contract = wan_contract(config, shot, keyframe, quality)
            expected[contract["input_hash"]] = contract
    cache = CacheIndex(root / config["paths"]["cache_index"])
    outputs = root / config["paths"]["outputs"] / "shots"
    sidecars = sorted(directory.glob("*.json"))
    if not sidecars:
        raise ValueError(f"No Wan clip sidecars found in {directory}")
    imported = []
    for sidecar in sidecars:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        digest = metadata["input_hash"]
        contract = expected.get(digest)
        if contract is None or any(metadata.get(key) != value for key, value in contract.items()):
            raise ValueError(f"{sidecar.name} does not match the current Wan inputs")
        for name in ("latency_s", "gpu_minutes"):
            value = metadata.get(name)
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{sidecar.name} has invalid {name}")
        shot_id = contract["shot_id"]
        clip = sidecar.with_suffix(".mp4")
        source = clip.read_bytes()
        source_hash = hashlib.sha256(source).hexdigest()
        if source_hash != metadata["output_sha256"]:
            raise ValueError(f"{clip.name} failed SHA-256 verification")
        existing = cache.lookup("wan", shot_id, digest)
        if existing is not None and file_hash(existing) == source_hash:
            imported.append(existing)
            continue
        check_clip(clip, contract["params"], ffprobe)
        output = outputs / f"{shot_id}_{digest}.mp4"
        write_artifact(output, source)
        log_run(
            root / config["paths"]["run_log"], stage="shots", shot_id=shot_id,
            model=contract["model"], params=contract["params"], seed=contract["seed"],
            digest=digest, latency_s=metadata["latency_s"], gpu_minutes=metadata["gpu_minutes"],
            status="imported",
        )
        cache.record("wan", shot_id, digest, output)
        imported.append(output)
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_workdir_argument(parser)
    parser.add_argument("directory", type=Path, help="Downloaded media files and JSON sidecars")
    parser.add_argument("--stage", choices=("shots", "music"), default="shots")
    parser.add_argument("--shot", type=int, help="Read the current keyframe for one shot only")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(args.workdir)
        if args.stage == "music":
            if args.shot is not None:
                parser.error("--shot applies to Wan clips")
            tracks = import_music(args.workdir, config, storyboard, args.directory, ffprobe=args.ffprobe)
            print(f"Verified {len(tracks)} ACE-Step candidate(s)")
        else:
            pairs = shot_inputs(args.workdir, config, storyboard, args.shot)
            clips = import_wan(args.workdir, config, pairs, args.directory, ffprobe=args.ffprobe)
            print(f"Verified {len(clips)} Wan clip(s)")
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
