"use client";

import { useEffect, useRef, useState } from "react";
import {
  AudioLines, Captions, Mic2, Music2, Pause, Play, Repeat2, RotateCcw, RotateCw, Volume2, VolumeX,
} from "lucide-react";
import { API, jobUrl, request, type RadioDetails, type Storyboard } from "../api";
import { mediaTime, skipMedia } from "./media-time";

export function RadioPlayer({ job, storyboard }: { job: string; storyboard: Storyboard | null }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [review, setReview] = useState<RadioDetails | null>(null);
  const [reviewError, setReviewError] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const [rate, setRate] = useState(1);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [playbackError, setPlaybackError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    request<RadioDetails>(jobUrl(job, "radio/details"), { signal: controller.signal })
      .then(setReview)
      .catch(() => { if (!controller.signal.aborted) setReviewError(true); });
    return () => controller.abort();
  }, [job]);

  const length = duration || review?.duration || 0;
  const played = length ? Math.min(1, elapsed / length) : 0;
  const cues = review?.cues ?? [];
  const activeCue = cues.find((cue) => elapsed >= cue.start && elapsed < cue.end);
  const cueIndex = Math.max(0, cues.findLastIndex((cue) => cue.start <= elapsed));
  const current = cues[cueIndex];
  const previous = cues[cueIndex - 1];
  const next = cues[cueIndex + 1];

  function seek(seconds: number) {
    if (audio.current && Number.isFinite(audio.current.duration)) {
      audio.current.currentTime = seconds;
      setElapsed(seconds);
    }
  }

  function playPause() {
    const player = audio.current;
    if (!player) return;
    if (!player.paused) {
      player.pause();
      return;
    }
    setPlaybackError("");
    void player.play().catch((error: DOMException) => {
      if (error.name !== "AbortError") setPlaybackError("The radio cut couldn’t play. Try pressing play again.");
    });
  }

  function changeRate(speed: number) {
    if (audio.current) audio.current.playbackRate = speed;
    setRate(speed);
  }

  return <div className="screening-stack">
    <section className="panel listening-panel" aria-label="Radio cut player">
      <div className="listening-title">
        <span className="production-icon"><AudioLines size={22} /></span>
        <div>
          <h2>{storyboard?.title ?? "Narration preview"}</h2>
          {storyboard && <p>{storyboard.shots.length} shots · {storyboard.language === "am" ? "Amharic" : "English"} narration</p>}
        </div>
        <button className="caption-switch" type="button" aria-pressed={captions} disabled={!cues.length}
          onClick={() => setCaptions((value) => !value)}>
          <Captions size={16} /> <span>Captions {captions ? "on" : "off"}</span>
        </button>
      </div>

      <div className="waveform">
        <div className="waveform-heading">
          <span><AudioLines size={14} /> Radio mix</span>
          {review && <span>{review.sample_rate / 1000} kHz · {review.channels === 1 ? "Mono" : "Stereo"}</span>}
        </div>
        <div className="waveform-canvas">
          {review?.peaks.length ? <>
            <div className="waveform-bars" aria-hidden="true">
              {review.peaks.map((peak, index) => <span key={index} className={index / review.peaks.length < played ? "played" : undefined}
                style={{ height: `${Math.max(4, peak * 100)}%` }} />)}
            </div>
            <span className="waveform-playhead" style={{ left: `${played * 100}%` }} aria-hidden="true" />
          </> : <p className="waveform-empty">{reviewError ? "Waveform unavailable" : "Loading waveform…"}</p>}
          <input className="waveform-seek" type="range" min={0} max={length || 1} step={.1} value={elapsed}
            disabled={!duration} aria-label="Seek in the radio cut" aria-valuetext={mediaTime(elapsed)}
            onChange={(event) => seek(Number(event.target.value))} />
        </div>
        <div className="waveform-time">
          <span>{mediaTime(elapsed)}</span>
          {captions && activeCue && <span className="waveform-caption">{activeCue.text}</span>}
          <span>{mediaTime(length)}</span>
        </div>
      </div>

      <audio ref={audio} preload="metadata" src={API + jobUrl(job, "radio")} loop={repeat}
        aria-label="Narration preview"
        onLoadedMetadata={(event) => setDuration(Number.isFinite(event.currentTarget.duration) ? event.currentTarget.duration : 0)}
        onTimeUpdate={(event) => setElapsed(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onVolumeChange={(event) => {
          setVolume(event.currentTarget.volume);
          setMuted(event.currentTarget.muted);
        }}
        onError={() => setPlaybackError("The radio cut audio could not be loaded.")} />

      <div className="listening-controls" aria-label="Radio cut playback controls">
        <div className="transport-buttons">
          <button className="media-icon" type="button" aria-label="Back 10 seconds" onClick={() => skipMedia(audio.current, -10)} disabled={!duration}><RotateCcw size={18} /></button>
          <button className="round-play" type="button" aria-label={playing ? "Pause radio cut" : "Play radio cut"} onClick={playPause}>
            {playing ? <Pause size={19} fill="currentColor" /> : <Play size={19} fill="currentColor" />}
          </button>
          <button className="media-icon" type="button" aria-label="Forward 10 seconds" onClick={() => skipMedia(audio.current, 10)} disabled={!duration}><RotateCw size={18} /></button>
          <button className="media-icon" type="button" aria-label="Repeat radio cut" aria-pressed={repeat} onClick={() => setRepeat((value) => !value)}><Repeat2 size={18} /></button>
        </div>
        <div className="listening-options">
          <div className="speed-control" role="group" aria-label="Playback speed">
            <span>Tempo</span>
            {[.8, 1, 1.2].map((speed) => <button key={speed} type="button" aria-pressed={rate === speed}
              onClick={() => changeRate(speed)}>{speed.toFixed(1)}×</button>)}
          </div>
          <div className="volume-control">
            <button className="media-icon" type="button" aria-label={muted ? "Unmute radio cut" : "Mute radio cut"}
              onClick={() => { if (audio.current) audio.current.muted = !muted; }}>
              {muted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
            </button>
            <input className="media-range" type="range" min={0} max={1} step={.01} value={muted ? 0 : volume} aria-label="Radio cut volume"
              onChange={(event) => {
                if (audio.current) {
                  audio.current.volume = Number(event.target.value);
                  audio.current.muted = false;
                }
              }} />
          </div>
        </div>
      </div>
      {playbackError && <p className="media-error" role="alert">{playbackError}</p>}

      <div className="listening-mix">
        <div><span><Mic2 size={15} /> Voice track</span><strong>Synthesized narration</strong></div>
        <div><span><Music2 size={15} /> Background score</span><strong>Temporary radio mix</strong></div>
      </div>
    </section>

    <section className="panel editorial-transcript" aria-labelledby="transcript-heading">
      <div className="transcript-heading">
        <h2 id="transcript-heading">Transcript</h2>
        {current && <span>{mediaTime(current.start)} – {mediaTime(current.end)}</span>}
      </div>
      {current && <>
        {previous && <p className="transcript-neighbor">{previous.text}</p>}
        <blockquote className="transcript-current">{current.text}</blockquote>
        {next && <p className="transcript-neighbor">{next.text}</p>}
      </>}
      {storyboard && <details open={!current}>
        <summary>Full narration</summary>
        {storyboard.shots.map((shot) => <p className="transcript-line" key={shot.id}>{shot.narration}</p>)}
      </details>}
    </section>
  </div>;
}
