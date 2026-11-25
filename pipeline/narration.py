"""Generate and cache one Gemini narration WAV per shot."""

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import re
from time import perf_counter
from urllib.error import HTTPError
import wave

from dotenv import load_dotenv
import yaml

from pipeline.providers import gemini_audio, post_json, speech_request
from pipeline.utils import CacheIndex, http_status, input_hash, log_run, retry, write_artifact
from pipeline.validate import ROOT, add_workdir_argument, validate_storyboard


class NarrationRateLimit(ValueError):
    def __init__(self, shot_id, daily=False):
        self.daily = daily
        super().__init__(f"Gemini speech {'daily quota reached' if daily else 'rate-limited'} at shot {shot_id}.")


def speech_retry_after(error):
    """Use Gemini's short retry hint and stop on a daily quota."""
    if not isinstance(error, HTTPError) or error.code != 429:
        return 0
    delay = 0.0
    header = error.headers.get("Retry-After", "") if error.headers else ""
    if re.fullmatch(r"[0-9]{1,8}", header):
        delay = float(header)
    try:
        details = json.loads(error.read()).get("error", {}).get("details", [])
    except (ValueError, OSError, AttributeError):
        details = []
    for detail in details:
        for violation in detail.get("violations", []):
            quota = re.sub(r"[^a-z]", "", str(violation.get("quotaId", "")).lower())
            if "perday" in quota or "daily" in quota:
                error.daily_quota = True
                return None
        hint = detail.get("retryDelay", "")
        if isinstance(hint, str) and re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,9})?s", hint):
            delay = max(delay, float(hint[:-1]))
    return (delay or 60) if delay <= 65 else None


def load_project(root):
    config_path = root / "config.yaml"
    if root != ROOT and not config_path.exists():
        config_path = ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
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


def generate_narration(root, config, storyboard, *, shot_id=None, cached_only=False, on_shot=None):
    settings = config["providers"]["narration"]
    model = settings["model"]
    endpoint = settings["endpoint"].format(model=model)
    cache = CacheIndex(root / config["paths"]["cache_index"])
    log_path = root / config["paths"]["run_log"]
    load_dotenv(ROOT / ".env")
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
            if on_shot is not None:
                on_shot(identifier)
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
            audio = retry(request_audio, max_attempts=config["retry"]["max_attempts"],
                          retry_after=speech_retry_after)
        except Exception as error:
            status = http_status(error)
            if status == 429:
                if not hasattr(error, "daily_quota") and isinstance(error, HTTPError):
                    speech_retry_after(error)
                raise NarrationRateLimit(identifier, daily=getattr(error, "daily_quota", False)) from None
            detail = f"HTTP {status}" if status else type(error).__name__
            raise ValueError(f"Shot {identifier} narration failed ({detail})") from None
        output = root / config["paths"]["outputs"] / "narration" / f"{identifier}_{digest}.wav"
        write_artifact(output, audio)
        cache.record("narration", identifier, digest, output)
        artifacts.append(output)
        if on_shot is not None:
            on_shot(identifier)
        print(f"Saved narration for shot {identifier}")
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_workdir_argument(parser)
    parser.add_argument("--shot", type=int, help="Generate only this shot ID")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(args.workdir)
        paths = generate_narration(args.workdir, config, storyboard, shot_id=args.shot)
    except (ValueError, OSError, KeyError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Narration ready for {len(paths)} shot(s)")


if __name__ == "__main__":
    main()
