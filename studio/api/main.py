"""Local HTTP API for Heritage Studio."""

import asyncio
from contextlib import asynccontextmanager, suppress
from io import BytesIO
import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
import yaml

from pipeline.utils import locked_file
from pipeline.validate import ROOT
from studio.api.jobs import CONSENT, PRIVACY, STAGES, Jobs, read_json, save_json
from studio.api.workflow import run_job, validate_job_storyboard


MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_PHOTOS * MAX_PHOTO_BYTES + 512 * 1024


class Feedback(BaseModel):
    laughed: str = Field(default="", max_length=2000)
    confused: str = Field(default="", max_length=2000)


def prepare_photos(photos):
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(413, "Upload up to 10 photos")
    normalized = []
    for number, photo in enumerate(photos, start=1):
        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Each photo must be 8 MB or smaller")
        try:
            with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
                if image.width * image.height > 30_000_000 or getattr(image, "is_animated", False):
                    raise ValueError("Unsupported image size or animation")
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((480, 480))
                clean = Image.new("RGB", image.size)
                clean.paste(image)
                buffer = BytesIO()
                clean.save(buffer, format="JPEG", quality=90)
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, TypeError, ValueError):
            raise HTTPException(422, "Upload a valid JPG, PNG, or WebP still image") from None
        normalized.append((f"photo-{number}.jpg", buffer.getvalue()))
    return normalized


def create_app(jobs_dir=None, config=None):
    if config is None:
        config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    store = Jobs(jobs_dir or ROOT / "jobs", config["studio"])

    async def clean_expired():
        while True:
            await asyncio.sleep(300)
            await asyncio.to_thread(store.cleanup)

    @asynccontextmanager
    async def lifespan(_app):
        await asyncio.to_thread(store.cleanup, recover=True)
        cleaner = asyncio.create_task(clean_expired())
        try:
            yield
        finally:
            cleaner.cancel()
            with suppress(asyncio.CancelledError):
                await cleaner

    api = FastAPI(title="Heritage Studio API", lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"],
    )

    @api.middleware("http")
    async def reject_oversize_requests(request, call_next):
        length = request.headers.get("content-length")
        if length is not None and (not length.isdecimal() or int(length) > MAX_REQUEST_BYTES):
            return JSONResponse({"detail": "The upload is too large"}, status_code=413)
        return await call_next(request)

    @api.get("/api/config")
    def studio_config():
        return {"consent": CONSENT, "privacy_note": PRIVACY, "max_photos": MAX_PHOTOS,
                "max_photo_bytes": MAX_PHOTO_BYTES, "retention_hours": config["studio"]["retention_hours"]}

    @api.post("/api/jobs", status_code=201)
    def create_job(
        request: Request,
        story: Annotated[str, Form(min_length=1, max_length=12000)],
        language: Annotated[Literal["en", "am"], Form()] = "en",
        consent: Annotated[bool, Form()] = False,
        privacy_acknowledged: Annotated[bool, Form()] = False,
        photos: Annotated[list[UploadFile] | None, File()] = None,
    ):
        if not consent:
            raise HTTPException(403, "Confirm that everyone shown or voiced has agreed")
        if photos and not privacy_acknowledged:
            raise HTTPException(403, "Acknowledge the privacy note before uploading photos")
        if not story.strip():
            raise HTTPException(422, "Enter a story before creating the job")
        uploads = prepare_photos(photos or [])
        store.consume("jobs", request.client.host if request.client else "local")
        return {"job_id": store.create(story.strip(), language, uploads, privacy_acknowledged)}

    def enqueue(identifier, action, tasks):
        job = store.job(identifier)
        with locked_file(store.lock):
            store.require_consent(job)
            status = store.status(job)
            if status["busy"]:
                raise HTTPException(409, "A stage is already running for this job")
            state = status["state"]
            if action == "draft" and state not in {"created", "failed", "storyboard_drafted"}:
                raise HTTPException(409, "This job already has an approved storyboard")
            if action in {"radio", "generate"} and not status.get("approved"):
                raise HTTPException(409, "Approve the storyboard first")
            if action == "generate" and not status.get("radio"):
                raise HTTPException(409, "Prepare the radio cut first")
            if action == "draft":
                status.update(approved=False, radio=None, downloads=None)
            elif action == "radio":
                status.update(downloads=None)
            status.update(busy=True, action=action, current_stage=action, state="generating", error=None)
            store.save_status(job, status)
        tasks.add_task(run_job, store, job, config, action)
        return {"job_id": identifier.hex, "state": "generating", "current_stage": action}

    @api.post("/api/jobs/{job_id}/storyboard/draft", status_code=202)
    def draft(job_id: UUID, tasks: BackgroundTasks):
        return enqueue(job_id, "draft", tasks)

    @api.get("/api/jobs/{job_id}/storyboard")
    def get_storyboard(job_id: UUID):
        job = store.job(job_id)
        try:
            return read_json(job / "storyboard.json")
        except FileNotFoundError:
            raise HTTPException(404, "The storyboard draft is not ready") from None

    @api.put("/api/jobs/{job_id}/storyboard")
    def save_storyboard(job_id: UUID, storyboard: dict, approve: bool = False):
        job = store.job(job_id)
        with locked_file(store.lock):
            status = store.status(job)
            if status["busy"]:
                raise HTTPException(409, "Wait for the current stage before editing")
            if approve:
                store.require_consent(job)
            try:
                validate_job_storyboard(job, storyboard)
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise HTTPException(422, str(error)) from None
            save_json(job / "storyboard.json", storyboard)
            state = "storyboard_approved" if approve else "storyboard_drafted"
            store.save_status(job, {
                **status, "state": state, "approved": approve, "radio": None, "downloads": None,
                "current_stage": None, "error": None, "stages": dict.fromkeys(STAGES, "pending"),
                "shots": {}, "timings_s": {},
            })
        return {"state": state}

    @api.post("/api/jobs/{job_id}/radio", status_code=202)
    def radio(job_id: UUID, tasks: BackgroundTasks):
        return enqueue(job_id, "radio", tasks)

    def release(job, relative, media_type, filename=None):
        if isinstance(relative, str):
            path = (job / relative).resolve()
            if path.is_relative_to(job) and path.is_file():
                return FileResponse(path, media_type=media_type, filename=filename)
        raise HTTPException(404, "This export is not ready")

    @api.get("/api/jobs/{job_id}/radio")
    def radio_file(job_id: UUID):
        job = store.job(job_id)
        return release(job, store.status(job).get("radio"), "video/mp4")

    @api.post("/api/jobs/{job_id}/feedback")
    def feedback(job_id: UUID, notes: Feedback):
        job = store.job(job_id)
        with locked_file(store.lock):
            if not store.status(job).get("radio"):
                raise HTTPException(409, "Prepare the radio cut before leaving feedback")
            save_json(job / "feedback.json", notes.model_dump())
        return {"saved": True}

    @api.post("/api/jobs/{job_id}/generate", status_code=202)
    def generate(job_id: UUID, tasks: BackgroundTasks):
        return enqueue(job_id, "generate", tasks)

    @api.get("/api/jobs/{job_id}/status")
    def status(job_id: UUID):
        return store.status(store.job(job_id))

    @api.get("/api/jobs/{job_id}/download/{kind}")
    def download(job_id: UUID, kind: Literal["vertical", "horizontal", "srt"]):
        job = store.job(job_id)
        status = store.status(job)
        name = "captions.srt" if kind == "srt" else f"{kind}.mp4"
        media_type = "application/x-subrip" if kind == "srt" else "video/mp4"
        return release(job, (status.get("downloads") or {}).get(name), media_type, name)

    @api.get("/api/jobs/{job_id}/preview/{kind}")
    def preview(job_id: UUID, kind: Literal["vertical", "horizontal"]):
        job = store.job(job_id)
        downloads = store.status(job).get("downloads") or {}
        return release(job, downloads.get(f"{kind}.mp4"), "video/mp4")

    return api


app = create_app()
