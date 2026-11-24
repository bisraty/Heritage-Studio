"""Render narration and a quiet placeholder score over black."""

import argparse
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from textwrap import wrap
import wave

import yaml

from pipeline.narration import generate_narration, load_project, narration_pcm
from pipeline.utils import CacheIndex, input_hash
from pipeline.validate import ROOT


SAMPLE_RATE = 24000
PLACEHOLDER_SCORE = (
    "aevalsrc=(sin(2*PI*110*t)+sin(2*PI*164.81*t)+sin(2*PI*220*t))"
    "*(0.65+0.35*cos(2*PI*0.4*t))/3:s=24000"
)


def srt_time(frames):
    milliseconds = round(frames * 1000 / SAMPLE_RATE)
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def prepare_tracks(work, shots, artifacts, padding_s, *, fps=None, tail_s=0):
    position = 0
    subtitles = []
    shot_frames = []
    with wave.open(str(work / "narration.wav"), "wb") as track:
        track.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        for shot, artifact in zip(shots, artifacts, strict=True):
            pcm = narration_pcm(str(artifact))
            frames = len(pcm) // 2
            total_frames = max(round(shot["duration_s"] * SAMPLE_RATE),
                               frames + round(padding_s * SAMPLE_RATE))
            if fps is not None:
                video_frames = math.ceil(total_frames * fps / SAMPLE_RATE)
                shot_frames.append(video_frames)
                total_frames = round(video_frames * SAMPLE_RATE / fps)
            track.writeframes(pcm)
            track.writeframes(bytes(2 * (total_frames - frames)))
            lines = wrap(shot["narration"], width=40, break_on_hyphens=False)
            groups = [lines[index:index + 2] for index in range(0, len(lines), 2)]
            caption_frames = max(frames, round(min(shot["duration_s"], 1) * SAMPLE_RATE))
            for index, group in enumerate(groups):
                start = srt_time(position + caption_frames * index // len(groups))
                end = srt_time(position + caption_frames * (index + 1) // len(groups))
                text = "\n".join(group)
                subtitles.append(f"{len(subtitles) + 1}\n{start} --> {end}\n{text}\n")
            position += total_frames
        tail_frames = round(tail_s * SAMPLE_RATE)
        track.writeframes(bytes(2 * tail_frames))
        position += tail_frames
    (work / "captions.srt").write_text("\n".join(subtitles), encoding="utf-8")
    return position / SAMPLE_RATE, shot_frames


def render_radio(root, config, storyboard, artifacts, *, ffmpeg="ffmpeg"):
    settings = config["radio"]
    assembly = config["assembly"]
    shots = storyboard["shots"]
    language = {"en": "eng", "am": "amh"}[storyboard["language"]]
    digest = input_hash(
        {"shots": [[shot["duration_s"], shot["narration"]] for shot in shots],
         "language": language, "settings": settings, "fps": assembly["fps"],
         "padding_s": assembly["narration_padding_s"], "video_codec": assembly["video_codec"],
         "audio_codec": assembly["audio_codec"], "score": PLACEHOLDER_SCORE},
        files=artifacts,
    )
    cache = CacheIndex(root / config["paths"]["cache_index"])
    existing = cache.lookup("radio", None, digest)
    if existing is not None:
        return existing

    output = root / config["paths"]["outputs"] / "radio" / f"radio_{digest}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        work = Path(directory)
        duration, _ = prepare_tracks(work, shots, artifacts, assembly["narration_padding_s"])
        video = f"color=black:s={settings['width']}x{settings['height']}:r={assembly['fps']}"
        audio = (f"[2:a]volume={settings['music_gain']}[score];"
                 "[1:a][score]amix=inputs=2:duration=first:normalize=0[radio]")
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
             "-f", "lavfi", "-i", video, "-i", "narration.wav",
             "-f", "lavfi", "-i", PLACEHOLDER_SCORE, "-i", "captions.srt",
             "-filter_complex", audio, "-map", "0:v", "-map", "[radio]", "-map", "3:s:0",
             "-c:v", assembly["video_codec"], "-pix_fmt", "yuv420p",
             "-c:a", assembly["audio_codec"], "-c:s", "mov_text", "-disposition:s:0", "default",
             "-metadata:s:s:0", f"language={language}",
             "-t", str(duration), "-movflags", "+faststart", "radio.mp4"],
            cwd=work, check=True,
        )
        (work / "radio.mp4").replace(output)
    cache.record("radio", None, digest, output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(ROOT)
        artifacts = generate_narration(ROOT, config, storyboard)
        output = render_radio(ROOT, config, storyboard, artifacts, ffmpeg=args.ffmpeg)
    except (ValueError, OSError, KeyError, yaml.YAMLError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Radio cut ready at {output}")


if __name__ == "__main__":
    main()
