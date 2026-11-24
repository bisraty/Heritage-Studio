"""Assemble a captioned heritage film in both delivery aspect ratios."""

import argparse
import json
import math
import os
from pathlib import Path
import re
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory

import yaml

from pipeline.keyframes import Keyframes
from pipeline.music import selected_music
from pipeline.narration import generate_narration, load_project
from pipeline.radio import PLACEHOLDER_SCORE, prepare_tracks
from pipeline.shots import generate_shots
from pipeline.utils import CacheIndex, input_hash, write_artifact
from pipeline.validate import ROOT


def run_ffmpeg(ffmpeg, work, *args, capture_output=False):
    return subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", *args],
        cwd=work, check=True, capture_output=capture_output, text=capture_output,
        encoding="utf-8" if capture_output else None, errors="replace" if capture_output else None,
    )


def mix_audio(work, assembly, duration, score, ffmpeg):
    music_input = ["-stream_loop", "-1", "-i", str(score.resolve())] if score else [
        "-f", "lavfi", "-i", PLACEHOLDER_SCORE,
    ]
    ducking = assembly["ducking"]
    narration_level = assembly["narration_lufs"]
    music_level = assembly["music_lufs"]
    fade = min(duration, assembly["end_card"]["duration_s"])
    filters = (
        f"[0:a]loudnorm=I={narration_level}:TP=-2:LRA=7,"
        "aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voice][sidechain];"
        f"[1:a]atrim=duration={duration},loudnorm=I={music_level}:TP=-2:LRA=7,"
        "aformat=sample_rates=48000:channel_layouts=stereo[music];"
        f"[music][sidechain]sidechaincompress=threshold={ducking['threshold']}:"
        f"ratio={ducking['ratio']}:attack={ducking['attack_ms']}:release={ducking['release_ms']},"
        f"afade=t=out:st={duration - fade}:d={fade}[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0[mix]"
    )
    run_ffmpeg(
        ffmpeg, work, "-loglevel", "error", "-i", "narration.wav", *music_input,
        "-filter_complex", filters, "-map", "[mix]", "-t", str(duration),
        "-c:a", "pcm_f32le", "mix.wav",
    )
    target = (
        f"loudnorm=I={assembly['loudness_lufs']}:TP={assembly['true_peak_dbtp']}:"
        f"LRA={assembly['loudness_range_lu']}"
    )
    first = run_ffmpeg(
        ffmpeg, work, "-i", "mix.wav", "-af", f"{target}:print_format=json",
        "-f", "null", "-", capture_output=True,
    )
    match = re.search(r'\{\s*"input_i".*?\}', first.stderr, re.DOTALL)
    if match is None:
        raise ValueError("FFmpeg did not produce a loudness measurement")
    levels = json.loads(match.group())
    fields = {"measured_I": "input_i", "measured_TP": "input_tp", "measured_LRA": "input_lra",
              "measured_thresh": "input_thresh", "offset": "target_offset"}
    if not all(math.isfinite(float(levels[name])) for name in fields.values()):
        raise ValueError("FFmpeg could not measure the loudness of the mix")
    measured = ":".join(f"{name}={levels[key]}" for name, key in fields.items())
    run_ffmpeg(
        ffmpeg, work, "-loglevel", "error", "-i", "mix.wav",
        "-af", f"{target}:{measured}:linear=true,aresample=48000",
        "-t", str(duration), "-c:a", assembly["audio_codec"], "-b:a", "192k", "soundtrack.m4a",
    )


def clip_length(path, ffprobe):
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=duration:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    metadata = json.loads(result.stdout)
    if not metadata.get("streams"):
        raise ValueError(f"No video stream in {path.name}")
    duration = float(metadata["streams"][0].get("duration", metadata["format"].get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"No usable video duration in {path.name}")
    return duration


def prepare_picture(work, assembly, clips, shot_frames, end_frames, ffmpeg, ffprobe):
    fps = assembly["fps"]
    size = min(min(size.values()) for size in assembly["exports"].values())
    segments = []
    common = ["-an", "-c:v", assembly["video_codec"], "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p"]
    for index, (clip, frame_count) in enumerate(zip(clips, shot_frames, strict=True)):
        available = max(1, round(clip_length(clip, ffprobe) * fps))
        trim = min(round(assembly["clip_trim_s"] * fps), (available - 1) // 2)
        end = available - trim
        picture = (
            f"fps={fps},trim=start_frame={trim}:end_frame={end},setpts=PTS-STARTPTS,"
            f"scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size},"
            f"setsar=1,tpad=stop_mode=clone:stop={frame_count}"
        )
        segment = f"shot-{index}.mp4"
        run_ffmpeg(
            ffmpeg, work, "-loglevel", "error", "-i", str(clip.resolve()), "-vf", picture,
            "-frames:v", str(frame_count), *common, segment,
        )
        segments.append(segment)
    run_ffmpeg(
        ffmpeg, work, "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s={size}x{size}:r={fps}",
        "-frames:v", str(end_frames), *common, "end.mp4",
    )
    (work / "picture.txt").write_text(
        "".join(f"file '{name}'\n" for name in [*segments, "end.mp4"]), encoding="ascii",
    )


def export_ratio(work, name, size, assembly, shot_frames, end_frames, titles, ffmpeg):
    width, height = size["width"], size["height"]
    portrait = height > width
    windows_font = Path(os.environ["WINDIR"]) / "Fonts" / "arial.ttf" if "WINDIR" in os.environ else None
    font = "font=Arial"
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)
    if windows_font is not None and windows_font.is_file():
        copyfile(windows_font, fonts / "overlay.ttf")
        font = "fontfile=fonts/overlay.ttf"
    caption_style = (
        f"FontName=Arial,FontSize={15 if portrait else 18},Outline=2,"
        f"Shadow=0,MarginV={40 if portrait else 22},Alignment=2"
    )
    filters = [
        f"fps={assembly['fps']},scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1",
        f"subtitles=captions.srt:fontsdir=fonts:force_style='{caption_style}'",
    ]
    position = 0
    for index, (frames, title) in enumerate(zip(shot_frames, titles, strict=True)):
        if title and title != "[APP NAME]":
            text_file = f"title-{index}.txt"
            (work / text_file).write_text(title, encoding="utf-8")
            filters.append(
                f"drawtext={font}:textfile={text_file}:expansion=none:fontcolor=white:"
                r"fontsize=min(w/23\,h/22):box=1:boxcolor=black@0.65:boxborderw=10:"
                f"x=(w-tw)/2:y=h/8:enable='between(n,{position},{position + frames - 1})'"
            )
        position += frames
    filters.append(
        f"drawtext={font}:textfile=end_card.txt:fontcolor=white:fontsize=h/18:"
        f"x=(w-tw)/2:y=(h-th)/2:enable='gte(n,{position})'"
    )
    run_ffmpeg(
        ffmpeg, work, "-loglevel", "error", "-f", "concat", "-safe", "1", "-i", "picture.txt",
        "-i", "soundtrack.m4a", "-vf", ",".join(filters), "-map", "0:v:0", "-map", "1:a:0",
        "-frames:v", str(position + end_frames), "-c:v", assembly["video_codec"],
        "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", f"{name}.mp4",
    )


def assemble(root, config, storyboard, narration, clips, score, *, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    assembly = config["assembly"]
    fps = assembly["fps"]
    end = assembly["end_card"]
    if end["text"] != "Made with AI" or not 2 <= end["duration_s"] <= 3:
        raise ValueError('The end card must read "Made with AI" and last 2–3 seconds')
    end_frames = round(end["duration_s"] * fps)
    shots = storyboard["shots"]
    titles = [shot.get("on_screen_text") for shot in shots]
    digest = input_hash(
        {"assembly": assembly, "shots": [[shot["duration_s"], shot["narration"]] for shot in shots],
         "titles": titles,
         "placeholder": PLACEHOLDER_SCORE if score is None else None},
        files=[*narration, *clips, *([score] if score is not None else [])],
    )
    cache = CacheIndex(root / config["paths"]["cache_index"])
    names = [*(f"{name}.mp4" for name in assembly["exports"]), "captions.srt"]
    existing = [cache.lookup("final", name, digest) for name in names]
    if all(path is not None for path in existing):
        return existing
    output = root / config["paths"]["outputs"] / "final" / digest
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        work = Path(directory)
        duration, shot_frames = prepare_tracks(
            work, shots, narration, assembly["narration_padding_s"], fps=fps, tail_s=end_frames / fps,
        )
        (work / "end_card.txt").write_text(end["text"], encoding="utf-8")
        mix_audio(work, assembly, duration, score, ffmpeg)
        prepare_picture(work, assembly, clips, shot_frames, end_frames, ffmpeg, ffprobe)
        for name, size in assembly["exports"].items():
            export_ratio(work, name, size, assembly, shot_frames, end_frames, titles, ffmpeg)
        output.mkdir(parents=True, exist_ok=True)
        for name in names:
            write_artifact(output / name, work / name)
            cache.record("final", name, digest, output / name)
    return [output / name for name in names]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--cached-only", action="store_true", help="Reuse narration and keyframes")
    modes.add_argument("--shot", type=int, help="Refresh only this shot's model outputs before assembly")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(ROOT)
        keyframes = Keyframes(ROOT, config, storyboard)
        score = selected_music(ROOT, config, storyboard)
        if args.shot is not None:
            keyframes.generate(args.shot)
            generate_narration(ROOT, config, storyboard, shot_id=args.shot)
        cached_only = args.cached_only or args.shot is not None
        frames = keyframes.generate(cached_only=cached_only)
        narration = generate_narration(ROOT, config, storyboard, cached_only=cached_only)
        clips = generate_shots(ROOT, config, list(zip(storyboard["shots"], frames, strict=True)), ffmpeg=args.ffmpeg)
        print(f"Score: {score if score is not None else 'temporary synthesized score'}")
        outputs = assemble(ROOT, config, storyboard, narration, clips, score,
                           ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"{error.stderr or error}\n")
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
