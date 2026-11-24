"""Adapters from persisted Studio jobs to shared pipeline stages."""

import json
import os
from time import perf_counter

from dotenv import load_dotenv
from fastapi import HTTPException

from pipeline.assemble import assemble
from pipeline.keyframes import Keyframes
from pipeline.music import selected_music
from pipeline.narration import generate_narration
from pipeline.providers import gemini_text, post_json, provider_budget
from pipeline.radio import render_radio
from pipeline.shots import generate_shots
from pipeline.utils import input_hash, log_run, retry, write_artifact
from pipeline.validate import ROOT, SCHEMA_PATH, validate_storyboard_data
from studio.api.jobs import read_json, save_json


def validate_job_storyboard(job, storyboard, *, draft=False):
    validate_storyboard_data(storyboard)
    if not 6 <= len(storyboard["shots"]) <= 10:
        raise ValueError("A Studio storyboard must have 6–10 shots")
    if storyboard["language"] != read_json(job / "input.json")["language"]:
        raise ValueError("Keep the job's selected language")
    if "character_reference" not in storyboard:
        raise ValueError("A Studio storyboard needs a character reference prompt and seeds")
    allowed = {f"uploads/{path.name}" for path in (job / "uploads").glob("*.jpg")}
    for shot in storyboard["shots"]:
        if len(shot["references"]) > 3 or any(path not in allowed for path in shot["references"]):
            raise ValueError(f"Shot {shot['id']} must reference at most three files uploaded to this job")
    if not storyboard["music"]["instrumental"]:
        raise ValueError("Studio scores must be instrumental")
    if draft:
        # Assign sanitized uploads in order as optional references for the user's review.
        for shot, image in zip(storyboard["shots"], sorted(allowed)):
            if not shot["references"]:
                shot["references"] = [image]
    return storyboard


def draft_storyboard(job, config):
    settings = config["providers"]["script"]
    model = settings["model"]
    endpoint = settings["endpoint"].format(model=model)
    load_dotenv(ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("Gemini credentials are missing")
    source = read_json(job / "input.json")
    payload = {
        "systemInstruction": {"parts": [{"text": config["studio"]["draft_instruction"]}]},
        "contents": [{"parts": [{"text": json.dumps({
            "story": source["story"], "language": source["language"], "schema": read_json(SCHEMA_PATH),
        }, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    digest = input_hash({"model": model, "payload": payload})
    event = dict(stage="script", shot_id=None, model=model, params={}, seed=None, digest=digest)
    log = job / config["paths"]["run_log"]

    def request():
        started = perf_counter()
        try:
            response = post_json(endpoint, {"x-goog-api-key": key}, payload, config["studio"]["draft_timeout_s"])
            storyboard = validate_job_storyboard(job, json.loads(gemini_text(response)), draft=True)
        except Exception as error:
            log_run(log, **event, status="failed", latency_s=perf_counter() - started, error=error)
            raise
        log_run(log, **event, status="ok", latency_s=perf_counter() - started)
        return storyboard

    return retry(request, max_attempts=config["retry"]["max_attempts"])


def make_reference(keyframes, job, storyboard):
    references = sorted((job / "uploads").glob("*.jpg"))[:1]
    character = storyboard["character_reference"]
    size = keyframes.settings["reference_size"]
    artifact = keyframes.get_image(
        "references", 1, keyframes.prompt(character["prompt"]), character["seeds"][0], size, size, references,
    )
    write_artifact(keyframes.golden, artifact)


def run_job(store, job, config, action):
    exhausted = False
    started = perf_counter()
    stage_started = {}

    def charge():
        nonlocal exhausted
        try:
            store.consume("model_calls")
        except HTTPException as error:
            exhausted = error.status_code == 429
            raise

    def progress(stage, state, shot=None):
        if shot is None and state == "running":
            stage_started[stage] = perf_counter()
        elapsed = perf_counter() - stage_started[stage] if state == "done" else None
        store.progress(job, stage, state, shot, elapsed_s=elapsed)

    try:
        store.require_consent(job)
        with provider_budget(charge):
            if action == "draft":
                storyboard = draft_storyboard(job, config)
                save_json(job / "storyboard.json", storyboard)
                timings = {**store.status(job)["timings_s"], "draft": perf_counter() - started}
                store.update(job, state="storyboard_drafted", busy=False, current_stage=None, timings_s=timings)
                return
            storyboard = validate_job_storyboard(job, read_json(job / "storyboard.json"))
            progress("narration", "running")
            narration = generate_narration(
                job, config, storyboard, on_shot=lambda shot: progress("narration", "running", shot),
            )
            progress("narration", "done")
            if action == "radio":
                preview = render_radio(job, config, storyboard, narration)
                timings = {**store.status(job)["timings_s"], "radio": perf_counter() - started}
                store.update(job, state="radio_ready", busy=False, current_stage=None,
                             radio=preview.relative_to(job).as_posix(), timings_s=timings)
                return
            progress("pictures", "running")
            keyframes = Keyframes(job, config, storyboard)
            make_reference(keyframes, job, storyboard)
            frames = keyframes.generate(on_shot=lambda shot: progress("pictures", "running", shot))
            clips = generate_shots(job, config, list(zip(storyboard["shots"], frames, strict=True)), prefer_wan=False)
            progress("pictures", "done")
            progress("music", "running")
            score = selected_music(job, config, storyboard)
            progress("music", "done")
            progress("edit", "running")
            artifacts = assemble(job, config, storyboard, narration, clips, score)
            downloads = {path.name: path.relative_to(job).as_posix() for path in artifacts}
            progress("edit", "done")
            store.update(job, state="done", busy=False, current_stage=None, downloads=downloads,
                         score="imported" if score else "placeholder", ai_label="Made with AI")
    except Exception as error:
        status = store.status(job)
        stage = status["current_stage"]
        message = ("Studio has reached its daily model-call limit. Try again tomorrow."
                   if exhausted else f"The {stage or action} stage could not finish ({type(error).__name__}). Retry the stage.")
        if stage in status["stages"]:
            status["stages"][stage] = "failed"
        timings = {**status["timings_s"], stage or action: perf_counter() - stage_started.get(stage, started)}
        store.update(job, state="failed", busy=False, error=message, stages=status["stages"], timings_s=timings)
