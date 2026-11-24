"""Generate and cache one Gemini narration WAV per shot."""

import argparse
from io import BytesIO
import os
from pathlib import Path
from time import perf_counter
import wave

from dotenv import load_dotenv
import yaml

from pipeline.providers import gemini_audio, post_json, speech_request
from pipeline.utils import CacheIndex, http_status, input_hash, log_run, retry, write_artifact
from pipeline.validate import ROOT, validate_storyboard


def load_project(root):
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    return config, validate_storyboard(root / config["paths"]["storyboard"])


def narration_pcm(source):
    """Read the documented Gemini PCM format and reject incomplete WAVs."""
    with wave.open(source, "rb") as audio:
        frames = audio.getnframes()
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
            raise ValueError("Expected 24 kHz mono 16-bit PCM narration")
        pcm = audio.readframes(frames)
    if not frames or len(pcm) != frames * 2:
        raise ValueError("Narration WAV contains incomplete PCM audio")
    return pcm


def generate_narration(root, config, storyboard, *, shot_id=None, cached_only=False):
    settings = config["providers"]["narration"]
    model = settings["model"]
    endpoint = settings["endpoint"].format(model=model)
    cache = CacheIndex(root / config["paths"]["cache_index"])
    log_path = root / config["paths"]["run_log"]
    load_dotenv(root / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    shots = [shot for shot in storyboard["shots"] if shot_id is None or shot["id"] == shot_id]
    if not shots:
        raise ValueError(f"Storyboard has no shot {shot_id}")

    artifacts = []
    for shot in shots:
        text = shot["narration"]
        payload = speech_request(model, text, settings["voice"], style=storyboard["narration_style"])
        digest = input_hash({"endpoint": endpoint, "payload": payload})
        identifier = shot["id"]
        event = dict(stage="narration", shot_id=identifier, model=model, params={}, seed=None, digest=digest)
        output = cache.lookup("narration", identifier, digest)
        if output is not None:
            log_run(log_path, **event, status="cache_hit", cache_hit=True)
            artifacts.append(output)
            continue
        if cached_only:
            raise ValueError(f"Narration for shot {identifier} is missing. Run the narration stage first.")
        if not api_key:
            raise ValueError("Set GEMINI_API_KEY in .env to generate uncached narration")

        def request_audio():
            start = perf_counter()
            try:
                response = post_json(endpoint, {"x-goog-api-key": api_key}, payload, settings["timeout_s"])
                audio = gemini_audio(response)
                narration_pcm(BytesIO(audio))
            except Exception as error:
                log_run(log_path, **event, status="failed", latency_s=perf_counter() - start, error=error)
                raise
            log_run(log_path, **event, status="ok", latency_s=perf_counter() - start)
            return audio

        try:
            audio = retry(request_audio, max_attempts=config["retry"]["max_attempts"])
        except Exception as error:
            status = http_status(error)
            detail = f"HTTP {status}" if status else type(error).__name__
            raise ValueError(f"Shot {identifier} narration failed ({detail})") from None
        output = root / config["paths"]["outputs"] / "narration" / f"{identifier}_{digest}.wav"
        write_artifact(output, audio)
        cache.record("narration", identifier, digest, output)
        artifacts.append(output)
        print(f"Saved narration for shot {identifier}")
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", type=int, help="Generate only this shot ID")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(ROOT)
        paths = generate_narration(ROOT, config, storyboard, shot_id=args.shot)
    except (ValueError, OSError, KeyError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Narration ready for {len(paths)} shot(s)")


if __name__ == "__main__":
    main()
