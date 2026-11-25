"""Expose listening metadata for the rendered radio cut."""

from array import array
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import wave

from pipeline.utils import locked_file, write_artifact
from studio.api.jobs import read_json, save_json


def seconds(timestamp):
    hours, minutes, rest = timestamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest.replace(",", "."))


def read_cues(path):
    cues = []
    for block in re.split(r"\n[ \t]*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) >= 3 and " --> " in lines[1]:
            start, end = lines[1].split(" --> ", 1)
            cues.append({"start": seconds(start), "end": seconds(end), "text": "\n".join(lines[2:])})
    return cues


def waveform(path):
    with wave.open(str(path), "rb") as stream:
        frames = stream.getnframes()
        sample_rate = stream.getframerate()
        channels = stream.getnchannels()
        peaks = []
        for bar in range(128):
            samples = array("h")
            samples.frombytes(stream.readframes((bar + 1) * frames // 128 - bar * frames // 128))
            if sys.byteorder != "little":
                samples.byteswap()
            peaks.append(max(map(abs, samples), default=0))
    highest = max(1, *peaks)
    return {"peaks": [round(peak / highest, 3) for peak in peaks],
            "duration": frames / sample_rate, "sample_rate": sample_rate, "channels": channels}


def radio_review(preview):
    """Derive a seekable waveform, caption cues and WAV from the existing MP4."""
    track = preview.with_suffix(".wav")
    details = preview.with_suffix(".review.json")
    with locked_file(details):
        if not track.is_file() or not details.is_file():
            with TemporaryDirectory(dir=preview.parent) as directory:
                temporary = Path(directory)
                audio = temporary / "mix.wav"
                captions = temporary / "captions.srt"
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(preview),
                     "-map", "0:a:0", "-c:a", "pcm_s16le", str(audio),
                     "-map", "0:s:0", "-f", "srt", str(captions)],
                    capture_output=True, check=True,
                )
                review = {**waveform(audio), "cues": read_cues(captions)}
                write_artifact(track, audio)
                save_json(details, review)
        return track, read_json(details)
