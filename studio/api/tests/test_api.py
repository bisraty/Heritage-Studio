from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient
from PIL import Image
import yaml

from pipeline.validate import ROOT
from studio.api.main import create_app


class StudioApiTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(TemporaryDirectory())
        self.root = Path(temp) / "jobs"
        self.config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.client = self.enterContext(TestClient(create_app(self.root, self.config)))
        self.storyboard = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
        self.storyboard["shots"] = self.storyboard["shots"][:6]

    def create_job(self, **data):
        response = self.client.post("/api/jobs", data={"story": "A family story", "consent": "true", **data})
        self.assertEqual(response.status_code, 201)
        return response.json()["job_id"]

    def test_requires_consent_for_job_and_generation(self):
        self.assertEqual(self.client.post("/api/jobs", data={"story": "A story"}).status_code, 403)
        identifier = self.create_job()
        path = f"/api/jobs/{identifier}"
        self.assertEqual(self.client.put(f"{path}/storyboard?approve=true", json=self.storyboard).status_code, 200)
        (self.root / identifier / "consent.json").unlink()
        for action in ("storyboard/draft", "radio", "generate"):
            self.assertEqual(self.client.post(f"{path}/{action}").status_code, 403)

    def test_edits_validate_before_replacing_approved_storyboard(self):
        identifier = self.create_job()
        path = f"/api/jobs/{identifier}"
        self.assertEqual(self.client.post(f"{path}/radio").status_code, 409)
        self.assertEqual(self.client.put(f"{path}/storyboard?approve=true", json=self.storyboard).status_code, 200)
        for field, value in (("duration_s", 0), ("references", ["../private.jpg"])):
            invalid = deepcopy(self.storyboard)
            invalid["shots"][0][field] = value
            self.assertEqual(self.client.put(f"{path}/storyboard", json=invalid).status_code, 422)
        self.assertEqual(self.client.get(f"{path}/storyboard").json(), self.storyboard)
        self.assertEqual(self.client.get(f"{path}/status").json()["state"], "storyboard_approved")

    def test_photos_require_privacy_acknowledgement_and_are_sanitized(self):
        source = BytesIO()
        image = Image.new("RGB", (960, 720), "orange")
        exif = image.getexif()
        exif[270] = "private description"
        image.save(source, "JPEG", exif=exif)
        data = {"story": "A story", "consent": "true"}
        files = [("photos", ("portrait.jpg", source.getvalue(), "image/jpeg"))]
        self.assertEqual(self.client.post("/api/jobs", data=data, files=files).status_code, 403)
        data["privacy_acknowledged"] = "true"
        invalid = [("photos", ("portrait.jpg", b"invalid image", "image/jpeg"))]
        self.assertEqual(self.client.post("/api/jobs", data=data, files=invalid).status_code, 422)
        response = self.client.post("/api/jobs", data=data, files=files)
        self.assertEqual(response.status_code, 201)
        with Image.open(self.root / response.json()["job_id"] / "uploads/photo-1.jpg") as stored:
            self.assertEqual(stored.size, (480, 360))
            self.assertFalse(stored.getexif())

    def test_job_creation_rate_limit_is_enforced(self):
        for _ in range(self.config["studio"]["jobs_per_ip_per_hour"]):
            self.create_job()
        response = self.client.post("/api/jobs", data={"story": "Another story", "consent": "true"})
        self.assertEqual(response.status_code, 429)

    def test_background_draft_exposes_status_and_validated_storyboard(self):
        identifier = self.create_job()
        path = f"/api/jobs/{identifier}"
        reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(self.storyboard)}]}}]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}), patch(
            "studio.api.workflow.post_json", return_value=reply,
        ) as request:
            self.assertEqual(self.client.post(f"{path}/storyboard/draft").status_code, 202)
            request.assert_called_once()
        status = self.client.get(f"{path}/status").json()
        self.assertEqual(status["state"], "storyboard_drafted")
        self.assertGreaterEqual(status["timings_s"]["draft"], 0)
        self.assertEqual(self.client.get(f"{path}/storyboard").json(), self.storyboard)

    def test_daily_call_cap_stops_the_request_before_network_access(self):
        identifier = self.create_job()
        path = f"/api/jobs/{identifier}"
        self.config["studio"]["daily_model_calls"] = 0
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}), patch(
            "pipeline.providers.build_opener",
        ) as opener:
            self.assertEqual(self.client.post(f"{path}/storyboard/draft").status_code, 202)
            opener.assert_not_called()
        status = self.client.get(f"{path}/status").json()
        self.assertEqual(status["state"], "failed")
        self.assertIn("daily model-call limit", status["error"])

    def test_draft_switches_models_after_provider_unavailable(self):
        identifier = self.create_job()
        path = f"/api/jobs/{identifier}"
        unavailable = HTTPError("https://example.test", 503, "Unavailable", {}, None)
        reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(self.storyboard)}]}}]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}), patch(
            "studio.api.workflow.post_json", side_effect=[unavailable, reply],
        ) as request, patch("pipeline.utils.time.sleep"):
            self.assertEqual(self.client.post(f"{path}/storyboard/draft").status_code, 202)
        self.assertEqual(self.client.get(f"{path}/status").json()["state"], "storyboard_drafted")
        self.assertEqual(request.call_count, 2)
        models = [self.config["providers"]["script"]["model"], self.config["studio"]["draft_fallback_model"]]
        for call, model in zip(request.call_args_list, models, strict=True):
            self.assertIn(f"/models/{model}:generateContent", call.args[0])
        entries = (self.root / identifier / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["model"] for line in entries], models)

    def test_unavailable_models_leave_an_editable_local_draft(self):
        story = "One family saved letters and photographs. Years later they made a film about the memories."
        identifier = self.create_job(story=story)
        path = f"/api/jobs/{identifier}"
        unavailable = HTTPError("https://example.test", 503, "Unavailable", {}, None)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}), patch(
            "studio.api.workflow.post_json", side_effect=unavailable,
        ) as request, patch("pipeline.utils.time.sleep"):
            self.assertEqual(self.client.post(f"{path}/storyboard/draft").status_code, 202)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(self.client.get(f"{path}/status").json()["draft_source"], "local")
        storyboard = self.client.get(f"{path}/storyboard").json()
        self.assertEqual(" ".join(shot["narration"] for shot in storyboard["shots"]), story)
        self.assertEqual(self.client.put(f"{path}/storyboard?approve=true", json=storyboard).status_code, 200)
