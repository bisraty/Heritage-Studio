"""Adapters from persisted Studio jobs to shared pipeline stages."""

import json
import os
import re
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
from pipeline.utils import http_status, input_hash, log_run, retry, write_artifact
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
    fallback = config["studio"].get("draft_fallback_model")
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
    log = job / config["paths"]["run_log"]

    def request():
        nonlocal model
        endpoint = settings["endpoint"].format(model=model)
        digest = input_hash({"model": model, "payload": payload})
        event = dict(stage="script", shot_id=None, model=model, params={}, seed=None, digest=digest)
        started = perf_counter()
        try:
            response = post_json(endpoint, {"x-goog-api-key": key}, payload, config["studio"]["draft_timeout_s"])
            storyboard = validate_job_storyboard(job, json.loads(gemini_text(response)), draft=True)
        except Exception as error:
            log_run(log, **event, status="failed", latency_s=perf_counter() - started, error=error)
            if http_status(error) == 503 and fallback:
                model = fallback
            raise
        log_run(log, **event, status="ok", latency_s=perf_counter() - started)
        return storyboard

    return retry(request, max_attempts=config["retry"]["max_attempts"])


def local_draft(job, config):
    """Build an editable storyboard from verbatim, ordered excerpts."""
    source = read_json(job / "input.json")
    words = source["story"].split()
    if len(words) < 6:
        raise ValueError("Add at least six words to create a local draft")
    settings = config["studio"]["local_draft"]
    count = min(10, max(6, (len(words) + 21) // 22))
    text = " ".join(words)
    boundaries = [0]
    for match in re.finditer(r"[.!?።፧]+[\"'”’)]*(?=\s)", text):
        position = text[:match.end()].count(" ") + 1
        boundaries.append(position)
    boundaries.append(len(words))
    shots = []
    for index in range(count):
        start = index * len(words) // count
        end = (index + 1) * len(words) // count
        # Use sentence boundaries when they are close to an even-length cut.
        if index:
            start = last_end
        if index + 1 < count:
            usable = [cut for cut in boundaries if start < cut <= len(words) - (count - index - 1)]
            near = min(usable, key=lambda cut: abs(cut - end), default=end)
            if abs(near - end) <= 4:
                end = near
        end = max(start + 1, end)
        last_end = end
        excerpt = " ".join(words[start:min(end, start + 22) if len(words) > 220 else end])
        shots.append({
            "id": index + 1, "duration_s": 7, "shot_size": "medium",
            "reason": ("Introduces the story." if index == 0 else
                       "Closes the story." if index == count - 1 else "Carries the story into its next moment."),
            "image_prompt": f"{settings['image_direction']} {excerpt}",
            "motion_prompt": settings["motion"][index % len(settings["motion"])],
            "narration": excerpt, "music_cue": "Keep the score soft beneath the narration.",
            "references": [], "seed": 1001 + index,
        })
    storyboard = {
        "title": " ".join(words[:6]).rstrip(",.;:!?።፧"),
        "language": source["language"], "style_prompt": settings["style"],
        "character_prompt": settings["character"], "narration_style": settings["narration_style"],
        "character_reference": {
            "prompt": settings["character_reference"], "continuity_prompt": settings["continuity"],
            "seeds": [2001, 2002, 2003, 2004],
        },
        "music": {"caption": settings["score_caption"], "instrumental": True,
                  "bpm": 90, "seeds": [3001, 3002, 3003]},
        "shots": shots,
    }
    return validate_job_storyboard(job, storyboard, draft=True)


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
                source = "gemini"
                try:
                    storyboard = draft_storyboard(job, config)
                except Exception as error:
                    if http_status(error) != 503:
                        raise
                    storyboard = local_draft(job, config)
                    source = "local"
                save_json(job / "storyboard.json", storyboard)
                timings = {**store.status(job)["timings_s"], "draft": perf_counter() - started}
                store.update(job, state="storyboard_drafted", busy=False, current_stage=None,
                             timings_s=timings, draft_source=source)
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
        if exhausted:
            message = "Studio has reached its daily model-call limit. Try again tomorrow."
        elif action == "draft" and http_status(error) == 503:
            message = "Gemini is busy. Your story is saved. Try drafting again in a few minutes."
        else:
            message = f"The {stage or action} stage could not finish ({type(error).__name__}). Retry the stage."
        if stage in status["stages"]:
            status["stages"][stage] = "failed"
        timings = {**status["timings_s"], stage or action: perf_counter() - stage_started.get(stage, started)}
        store.update(job, state="failed", busy=False, error=message, stages=status["stages"], timings_s=timings)
