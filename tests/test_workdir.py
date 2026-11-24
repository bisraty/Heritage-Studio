from base64 import b64encode
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from pipeline import narration
from pipeline.validate import ROOT


class WorkdirTests(unittest.TestCase):
    def test_narration_keeps_identical_jobs_in_separate_caches(self):
        samples = BytesIO()
        with wave.open(samples, "wb") as track:
            track.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            track.writeframes(b"\x01\x00" * 32)
        data = b64encode(samples.getvalue()).decode("ascii")
        response = {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": data}]}]}
        storyboard = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
        storyboard["shots"] = storyboard["shots"][:1]

        with TemporaryDirectory() as temporary, patch.dict("os.environ", {"GEMINI_API_KEY": "fixture"}):
            first, second = (Path(temporary) / folder for folder in ("first job", "second job"))
            for folder in (first, second):
                folder.mkdir()
                (folder / "storyboard.json").write_text(json.dumps(storyboard), encoding="utf-8")
            with patch.object(narration, "post_json", return_value=response) as request:
                for folder in (first, second, first):
                    with patch("sys.argv", ["narration", "--workdir", str(folder)]), redirect_stdout(StringIO()):
                        narration.main()
                self.assertEqual(request.call_count, 2)

            for folder, expected in ((first, ["ok", "cache_hit"]), (second, ["ok"])):
                self.assertTrue((folder / "outputs/cache_index.json").is_file())
                self.assertEqual(len(list((folder / "outputs/narration").glob("*.wav"))), 1)
                lines = (folder / "runs.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual([json.loads(line)["status"] for line in lines], expected)
