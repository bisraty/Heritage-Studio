"""Shared primitives for independently runnable film stages."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
from shutil import copyfileobj
from tempfile import NamedTemporaryFile
import time
from urllib.error import HTTPError, URLError

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def input_hash(inputs, *, files=()):
    """Hash JSON inputs and an ordered sequence of reference and upstream files."""
    payload = {"inputs": inputs, "file_hashes": [file_hash(path) for path in files]}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def write_artifact(path, data):
    """Publish complete bytes by replacing the destination from the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(dir=path.parent, delete=False)
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            if isinstance(data, Path):
                with data.open("rb") as source:
                    copyfileobj(source, temporary)
            else:
                temporary.write(data)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def locked_file(path):
    """Serialize writers across processes using a persistent sidecar lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


class CacheIndex:
    """Map stage, shot, and input hash to completed files under the outputs directory."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.outputs = self.path.parent

    def _read(self):
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        index = json.loads(content)
        if not isinstance(index, dict) or any(not isinstance(value, str) for value in index.values()):
            raise ValueError(f"{self.path} must map cache keys to output paths")
        return index

    def lookup(self, stage, shot_id, digest):
        key = canonical_json([stage, shot_id, digest])
        with locked_file(self.path):
            relative_path = self._read().get(key)
        if relative_path is None:
            return None
        output = (self.outputs / relative_path).resolve()
        if output.is_relative_to(self.outputs) and output.is_file():
            return output
        return None

    def record(self, stage, shot_id, digest, output):
        output = Path(output).resolve()
        relative_path = output.relative_to(self.outputs).as_posix()
        key = canonical_json([stage, shot_id, digest])
        with locked_file(self.path):
            if not output.is_file():
                raise FileNotFoundError(output)
            index = self._read()
            index[key] = relative_path
            temporary = NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.outputs, delete=False
            )
            temp_path = Path(temporary.name)
            try:
                with temporary:
                    temporary.write(canonical_json(index) + "\n")
                    temporary.flush()
                    os.fsync(temporary.fileno())
                temp_path.replace(self.path)
            finally:
                temp_path.unlink(missing_ok=True)


def http_status(error):
    if isinstance(error, HTTPError):
        return error.code
    return getattr(error, "status_code", None)


def is_transient(error):
    cause = error.reason if isinstance(error, URLError) else error
    status = http_status(error)
    return isinstance(cause, TimeoutError) or (
        isinstance(status, int) and (status == 429 or 500 <= status <= 599)
    )


def retry(operation, *, max_attempts=3, initial_delay_s=1.0, retry_after=None):
    """Retry transient failures and raise the last error for the stage fallback."""
    if not 1 <= max_attempts <= 3 or initial_delay_s <= 0:
        raise ValueError("Retry requires 1 to 3 attempts and a positive initial delay")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as error:
            if attempt == max_attempts or not is_transient(error):
                raise
            minimum = retry_after(error) if retry_after is not None else 0
            if minimum is None:
                raise
            delay = initial_delay_s * 2 ** (attempt - 1)
            time.sleep(max(delay, minimum) + random.uniform(0, delay))


def log_run(
    path, *, stage, shot_id, model, params, seed, digest, status,
    latency_s=None, cost_estimate_usd=None, gpu_minutes=None, cache_hit=False, error=None,
):
    """Append one event using configured model IDs and sanitized request metadata."""
    numeric_params = {
        "width", "height", "steps", "num_inference_steps", "guidance_scale",
        "temperature", "max_output_tokens", "duration_s", "fps", "bpm", "num_frames",
    }
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "params": {
            key: value
            for key, value in params.items()
            if key in numeric_params and type(value) in (int, float)
        },
        "seed": seed,
        "input_hash": digest,
        "latency_s": latency_s,
        "cost_estimate_usd": cost_estimate_usd,
        "gpu_minutes": gpu_minutes,
        "status": status,
        "cache_hit": cache_hit,
        "error": None if error is None else {
            "type": type(error).__name__,
            "http_status": http_status(error),
        },
    }
    path = Path(path)
    line = canonical_json(entry) + "\n"
    with locked_file(path), path.open("a", encoding="utf-8", newline="\n") as log:
        log.write(line)
