"""Filesystem job storage and shared limits for the local Studio API."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from fastapi import HTTPException

from pipeline.utils import canonical_json, locked_file, write_artifact


CONSENT = "Everyone shown or voiced in this film has agreed to it."
PRIVACY = "AI services may use free-tier inputs to improve their models. Leave out private details. Photos are used as illustration references."
STAGES = ("narration", "pictures", "music", "edit")


def now():
    return datetime.now(timezone.utc)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    write_artifact(path, (canonical_json(value) + "\n").encode("utf-8"))


class Jobs:
    def __init__(self, root, settings):
        self.root = Path(root).resolve()
        self.settings = settings
        self.lock = self.root / "store"
        self.limits = self.root / "limits.json"

    def create(self, story, language, photos, privacy_acknowledged):
        identifier = uuid4().hex
        job = self.root / identifier
        created = now().isoformat()
        with locked_file(self.lock):
            job.mkdir()
            for name, data in photos:
                write_artifact(job / "uploads" / name, data)
            save_json(job / "input.json", {"story": story, "language": language, "created_at": created})
            save_json(job / "consent.json", {
                "agreed": True, "wording": CONSENT, "recorded_at": created,
                "privacy_acknowledged": privacy_acknowledged, "privacy_note": PRIVACY,
            })
            self.save_status(job, {
                "state": "created", "current_stage": None, "error": None, "busy": False,
                "stages": dict.fromkeys(STAGES, "pending"), "shots": {}, "timings_s": {},
            })
        return identifier

    def job(self, identifier):
        job = self.root / identifier.hex
        if not (job / "status.json").is_file():
            raise HTTPException(404, "Film job not found")
        return job

    def require_consent(self, job):
        try:
            record = read_json(job / "consent.json")
            if (record["agreed"] is not True or record["wording"] != CONSENT
                    or datetime.fromisoformat(record["recorded_at"]).tzinfo is None
                    or (any((job / "uploads").glob("*.jpg"))
                        and (record.get("privacy_acknowledged") is not True
                             or record.get("privacy_note") != PRIVACY))):
                raise ValueError("Invalid consent")
        except (OSError, KeyError, TypeError, ValueError):
            raise HTTPException(403, "This job needs a valid consent record before generation") from None

    def status(self, job):
        try:
            return read_json(job / "status.json")
        except FileNotFoundError:
            raise HTTPException(404, "Film job not found") from None

    def save_status(self, job, status):
        save_json(job / "status.json", {**status, "updated_at": now().isoformat()})

    def update(self, job, **fields):
        with locked_file(self.lock):
            status = self.status(job)
            self.save_status(job, {**status, **fields})

    def progress(self, job, stage, status, shot=None, elapsed_s=None):
        with locked_file(self.lock):
            record = self.status(job)
            record["current_stage"] = stage
            record["stages"][stage] = status
            if shot is not None:
                record["shots"].setdefault(str(shot), {})[stage] = "done"
            if elapsed_s is not None:
                record["timings_s"][stage] = elapsed_s
            self.save_status(job, record)

    def consume(self, kind, client=None):
        instant = now()
        if kind == "jobs":
            window = instant.strftime("%Y-%m-%dT%H")
            key = hashlib.sha256(client.encode("utf-8")).hexdigest()
            limit = self.settings["jobs_per_ip_per_hour"]
        else:
            window = instant.strftime("%Y-%m-%d")
            key = "model_calls"
            limit = self.settings["daily_model_calls"]
        with locked_file(self.lock):
            limits = read_json(self.limits) if self.limits.is_file() else {}
            bucket = limits.get(kind, {})
            counts = bucket.get("counts", {}) if bucket.get("window") == window else {}
            if counts.get(key, 0) >= limit:
                raise HTTPException(429, "Studio has reached its usage limit. Please try again later.")
            counts[key] = counts.get(key, 0) + 1
            limits[kind] = {"window": window, "counts": counts}
            save_json(self.limits, limits)

    def cleanup(self, *, recover=False):
        cutoff = now() - timedelta(hours=self.settings["retention_hours"])
        with locked_file(self.lock):
            for job in self.root.iterdir():
                if job.is_symlink() or not job.is_dir() or job.resolve().parent != self.root:
                    continue
                if len(job.name) != 32 or any(char not in "0123456789abcdef" for char in job.name):
                    continue
                status_path = job / "status.json"
                if not status_path.is_file():
                    if datetime.fromtimestamp(job.stat().st_mtime, timezone.utc) < cutoff:
                        rmtree(job)
                    continue
                status = self.status(job)
                if recover and status["busy"]:
                    self.save_status(job, {
                        **status, "busy": False, "state": "failed",
                        "error": "The server restarted. Retry the interrupted stage.",
                    })
                elif not status["busy"] and datetime.fromisoformat(status["updated_at"]) < cutoff:
                    rmtree(job)
