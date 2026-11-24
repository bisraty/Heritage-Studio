"""Check text, speech, and image generation once each using synthetic inputs."""

import os
import sys
from time import perf_counter
from urllib.error import URLError

from dotenv import load_dotenv
import yaml

from pipeline.providers import (
    cloudflare_image, gemini_audio, gemini_text, post_json, speech_request,
)
from pipeline.utils import http_status, input_hash, log_run
from pipeline.validate import ROOT, validate_storyboard


def run_probe(stage, settings, endpoint, headers, payload, decode, timeout_s, log_path):
    model = settings["model"]
    digest = input_hash({"model": model, "payload": payload})
    started = perf_counter()
    error = None
    try:
        decode(post_json(endpoint, headers, payload, timeout_s))
    except (OSError, URLError, ValueError, TypeError, AttributeError) as failure:
        error = failure
    elapsed = perf_counter() - started
    log_run(
        log_path, stage=stage, shot_id=None, model=model, params=payload,
        seed=None, digest=digest, latency_s=elapsed,
        status="ok" if error is None else "failed", error=error,
    )
    if error is None:
        print(f"{stage} ({model}) passed in {elapsed:.2f}s")
        return True
    code = http_status(error)
    detail = f"HTTP {code}" if code is not None else type(error).__name__
    print(f"{stage} ({model}) failed after {elapsed:.2f}s ({detail})", file=sys.stderr)
    return False


def main():
    try:
        config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        validate_storyboard(ROOT / config["paths"]["storyboard"])
        load_dotenv(ROOT / ".env")
        smoke = config["smoke"]
        providers = config["providers"]
        log_path = ROOT / config["paths"]["run_log"]
        gemini = {"x-goog-api-key": os.getenv("GEMINI_API_KEY", "")}
        cloudflare = {
            "Authorization": f"Bearer {os.getenv('CLOUDFLARE_API_TOKEN', '')}",
        }
        probes = (
            ("script", ("GEMINI_API_KEY",), gemini,
             {"contents": [{"parts": [{"text": smoke["script_prompt"]}]}]}, gemini_text),
            ("narration", ("GEMINI_API_KEY",), gemini,
             speech_request(providers["narration"]["model"], smoke["narration_text"],
                            providers["narration"]["voice"]), gemini_audio),
            ("keyframes", ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"), cloudflare,
             {"prompt": smoke["keyframe_prompt"], "steps": smoke["keyframe_steps"]},
             cloudflare_image),
        )
        all_passed = True
        for stage, credential_names, headers, payload, decode in probes:
            missing = [name for name in credential_names if not os.getenv(name, "").strip()]
            if missing:
                print(f"{stage} skipped. Set {', '.join(missing)} in .env or the environment.",
                      file=sys.stderr)
                all_passed = False
                continue
            settings = providers[stage]
            if stage == "keyframes":
                settings = {**settings, "model": smoke["keyframe_model"]}
            endpoint = settings["endpoint"].format(
                model=settings["model"], account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
            )
            passed = run_probe(
                stage, settings, endpoint, headers, payload, decode, smoke["timeout_s"], log_path,
            )
            all_passed = passed and all_passed
        return 0 if all_passed else 1
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        print(f"Smoke setup failed ({type(error).__name__}). Check config.yaml, "
              "storyboard.json, and the run log path.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
