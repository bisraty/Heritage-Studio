from concurrent.futures import ThreadPoolExecutor
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError, URLError

from pipeline.narration import speech_retry_after
from pipeline.utils import CacheIndex, input_hash, log_run, retry


class HashTests(unittest.TestCase):
    def test_input_order_and_file_content(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.png"
            reference.write_bytes(b"first")
            original = input_hash({"seed": 2, "model": "model"}, files=[reference])
            self.assertEqual(
                original, input_hash({"model": "model", "seed": 2}, files=[reference])
            )
            self.assertNotEqual(
                original, input_hash({"model": "model", "seed": 3}, files=[reference])
            )
            reference.write_bytes(b"second")
            self.assertNotEqual(
                original, input_hash({"model": "model", "seed": 2}, files=[reference])
            )


class CacheTests(unittest.TestCase):
    def test_concurrent_records_are_preserved_and_missing_files_are_misses(self):
        with TemporaryDirectory() as directory:
            outputs = Path(directory) / "outputs"
            outputs.mkdir()
            path = outputs / "cache_index.json"
            cache = CacheIndex(path)

            def record(shot_id):
                output = outputs / f"{shot_id}_hash.wav"
                output.write_bytes(b"audio")
                CacheIndex(path).record("narration", shot_id, "hash", output)
                return output

            self.assertIsNone(cache.lookup("narration", 1, "hash"))
            with ThreadPoolExecutor(max_workers=3) as executor:
                artifacts = list(executor.map(record, range(1, 7)))
            for shot_id, artifact in enumerate(artifacts, start=1):
                self.assertEqual(cache.lookup("narration", shot_id, "hash"), artifact)
            self.assertIsNone(cache.lookup("keyframes", 1, "hash"))
            self.assertIsNone(cache.lookup("narration", 1, "changed"))
            artifacts[0].unlink()
            self.assertIsNone(cache.lookup("narration", 1, "hash"))
            with self.assertRaises(FileNotFoundError):
                cache.record("narration", 1, "hash", artifacts[0])
            with self.assertRaises(ValueError):
                cache.record("narration", 1, "hash", outputs.parent / "outside.wav")


class RetryTests(unittest.TestCase):
    @patch("pipeline.utils.random.uniform", return_value=0)
    @patch("pipeline.utils.time.sleep")
    def test_speech_retry_waits_for_gemini_and_stops_on_daily_quota(self, sleep, jitter):
        def error(detail):
            body = BytesIO(json.dumps({"error": {"details": [detail]}}).encode())
            return HTTPError("https://example.test", 429, "quota", {}, body)

        operation = Mock(side_effect=[error({"retryDelay": "42.5s"}), "audio"])
        self.assertEqual(retry(operation, retry_after=speech_retry_after), "audio")
        sleep.assert_called_once_with(42.5)
        daily = error({"violations": [{"quotaId": "RequestsPerDayPerProject"}]})
        operation = Mock(side_effect=daily)
        with self.assertRaises(HTTPError):
            retry(operation, retry_after=speech_retry_after)
        operation.assert_called_once()
        self.assertTrue(daily.daily_quota)

    @patch("pipeline.utils.random.uniform", return_value=0.5)
    @patch("pipeline.utils.time.sleep")
    def test_transient_failures_back_off(self, sleep, jitter):
        rate_limit = HTTPError("https://example.test", 429, "rate limit", {}, None)
        operation = Mock(side_effect=[rate_limit, URLError(TimeoutError()), "done"])
        self.assertEqual(retry(operation), "done")
        self.assertEqual(sleep.call_args_list, [call(1.5), call(2.5)])
        self.assertEqual(jitter.call_args_list, [call(0, 1.0), call(0, 2.0)])

    @patch("pipeline.utils.time.sleep")
    def test_three_attempts_at_most_and_no_retry_on_client_error(self, sleep):
        for code, expected_calls in [(503, 3), (400, 1)]:
            with self.subTest(code=code):
                error = HTTPError("https://example.test", code, "failure", {}, None)
                operation = Mock(side_effect=error)
                with self.assertRaises(HTTPError) as caught:
                    retry(operation)
                self.assertIs(caught.exception, error)
                self.assertEqual(operation.call_count, expected_calls)
        self.assertEqual(sleep.call_count, 2)


class RunLogTests(unittest.TestCase):
    def test_appends_json_lines_without_private_values_or_fake_metrics(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            meta = {
                "stage": "keyframes", "shot_id": 1, "model": "model-a", "seed": 12,
                "digest": "hash", "params": {"width": 1080, "prompt": "private story"},
            }
            failure = HTTPError("https://example.test", 503, "private response", {}, None)
            log_run(path, **meta, status="failed", error=failure, latency_s=0.25)
            log_run(path, **meta, status="cache_hit", cache_hit=True)
            raw = path.read_text(encoding="utf-8")
            first, second = (json.loads(line) for line in raw.splitlines())
            self.assertNotIn("private", raw)
            self.assertEqual(first["params"], {"width": 1080})
            self.assertEqual(first["error"], {"type": "HTTPError", "http_status": 503})
            self.assertEqual(first["input_hash"], "hash")
            self.assertEqual(first["latency_s"], 0.25)
            self.assertIsNone(first["cost_estimate_usd"])
            self.assertIsNone(first["gpu_minutes"])
            self.assertTrue(second["cache_hit"])
            self.assertIsNone(second["error"])


if __name__ == "__main__":
    unittest.main()
