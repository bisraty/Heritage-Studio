"""Prepare, import, and select ACE-Step score candidates."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import yaml

from pipeline.narration import load_project
from pipeline.utils import CacheIndex, canonical_json, file_hash, input_hash, log_run, write_artifact
from pipeline.validate import add_workdir_argument


def music_contracts(config, storyboard):
    brief = storyboard["music"]
    provider = config["providers"]["music"]
    seeds = brief.get("seeds", [])
    if len(seeds) != provider["candidates"]:
        raise ValueError(f"Set {provider['candidates']} music seeds in storyboard.json")
    if not brief["instrumental"] or not 30 <= brief["bpm"] <= 300 or len(brief["caption"]) > 512:
        raise ValueError("The score must be instrumental with 30–300 BPM and a caption up to 512 characters")
    for option, seed in enumerate(seeds, start=1):
        contract = {
            "candidate": option, "model": provider["model"], "seed": seed,
            "caption_hash": input_hash(brief["caption"]),
            "params": {
                "bpm": brief["bpm"], "instrumental": True,
                "duration_s": provider["duration_s"], "inference_steps": provider["inference_steps"],
            },
        }
        yield {**contract, "input_hash": input_hash(contract)}


def export_music_bundle(path, config, storyboard):
    bundle = {"caption": storyboard["music"]["caption"], "candidates": list(music_contracts(config, storyboard))}
    write_artifact(path, (canonical_json(bundle) + "\n").encode("utf-8"))


def check_audio(path, ffprobe):
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=duration:format=format_name", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    media = json.loads(result.stdout)
    streams = media.get("streams", [])
    if not streams or media.get("format", {}).get("format_name") != "wav":
        raise ValueError(f"{path.name} must contain WAV audio")
    duration = float(streams[0].get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"{path.name} must contain nonempty audio")


def import_music(root, config, storyboard, directory, *, ffprobe="ffprobe"):
    contracts = {contract["input_hash"]: contract for contract in music_contracts(config, storyboard)}
    cache = CacheIndex(root / config["paths"]["cache_index"])
    outputs = root / config["paths"]["outputs"] / "music"
    sidecars = sorted(directory.glob("*.json"))
    if not sidecars:
        raise ValueError(f"No ACE-Step candidate sidecars found in {directory}")
    imported = []
    for sidecar in sidecars:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        digest = metadata["input_hash"]
        contract = contracts.get(digest)
        if contract is None or any(metadata.get(key) != value for key, value in contract.items()):
            raise ValueError(f"{sidecar.name} does not match the current music brief")
        for name in ("latency_s", "gpu_minutes"):
            value = metadata.get(name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{sidecar.name} has invalid {name}")
        clip = sidecar.with_suffix(".wav")
        data = clip.read_bytes()
        digest_audio = hashlib.sha256(data).hexdigest()
        if digest_audio != metadata["output_sha256"]:
            raise ValueError(f"{clip.name} failed SHA-256 verification")
        option = contract["candidate"]
        existing = cache.lookup("music", option, digest)
        if existing and file_hash(existing) == digest_audio:
            imported.append(existing)
            continue
        check_audio(clip, ffprobe)
        output = outputs / f"{option}_{digest}.wav"
        write_artifact(output, data)
        log_run(
            root / config["paths"]["run_log"], stage="music", shot_id=None,
            model=contract["model"], params=contract["params"], seed=contract["seed"],
            digest=digest, status="imported", latency_s=metadata["latency_s"],
            gpu_minutes=metadata["gpu_minutes"],
        )
        cache.record("music", option, digest, output)
        imported.append(output)
    return imported


def selection_path(root, config):
    return root / config["paths"]["outputs"] / "music" / "selection.json"


def selected_music(root, config, storyboard):
    try:
        selection = json.loads(selection_path(root, config).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    for contract in music_contracts(config, storyboard):
        if contract["input_hash"] == selection["input_hash"]:
            cache = CacheIndex(root / config["paths"]["cache_index"])
            track = cache.lookup("music", contract["candidate"], contract["input_hash"])
            if track and file_hash(track) == selection["output_sha256"]:
                return track
    return None


def select_music(root, config, storyboard, option):
    cache = CacheIndex(root / config["paths"]["cache_index"])
    for contract in music_contracts(config, storyboard):
        if contract["candidate"] == option:
            digest = contract["input_hash"]
            track = cache.lookup("music", option, digest)
            if track is not None:
                data = {"candidate": option, "input_hash": digest, "output_sha256": file_hash(track)}
                write_artifact(selection_path(root, config), (canonical_json(data) + "\n").encode("utf-8"))
                return track
    raise ValueError(f"Current music candidate {option} is unavailable. Import it first.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_workdir_argument(parser)
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--export-ace", type=Path, metavar="MANIFEST")
    choices.add_argument("--select", type=int, metavar="NUMBER")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(args.workdir)
        if args.export_ace is not None:
            export_music_bundle(args.export_ace, config, storyboard)
            print(f"ACE-Step manifest ready at {args.export_ace}")
        elif args.select is not None:
            print(f"Selected music: {select_music(args.workdir, config, storyboard, args.select)}")
        else:
            cache = CacheIndex(args.workdir / config["paths"]["cache_index"])
            for entry in music_contracts(config, storyboard):
                number = entry["candidate"]
                path = cache.lookup("music", number, entry["input_hash"])
                print(f"Candidate {number}: {path or 'awaiting import'}")
            print(f"Selected music: {selected_music(args.workdir, config, storyboard) or 'awaiting selection'}")
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
