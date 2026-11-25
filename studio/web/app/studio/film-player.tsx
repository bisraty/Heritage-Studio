"use client";

import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Captions, Maximize, Minimize, Pause, Play, RotateCcw, Volume2, VolumeX } from "lucide-react";
import type { Orientation } from "../api";
import { mediaTime, skipMedia } from "./media-time";

export function FilmPlayer({
  orientation, src, poster, onDuration,
}: {
  orientation: Orientation;
  src: string;
  poster?: string;
  onDuration: (seconds: number) => void;
}) {
  const screen = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const transportPlay = useRef<HTMLButtonElement>(null);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [playbackError, setPlaybackError] = useState("");

  useEffect(() => {
    function syncFullscreen() {
      setFullscreen(document.fullscreenElement === screen.current);
    }
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  function playPause() {
    const player = video.current;
    if (!player) return;
    if (!player.paused) {
      player.pause();
      return;
    }
    setPlaybackError("");
    void player.play().catch((error: DOMException) => {
      if (error.name !== "AbortError") setPlaybackError("The film couldn’t play. Try pressing play again.");
    });
  }

  async function toggleFullscreen() {
    try {
      if (fullscreen) {
        await document.exitFullscreen();
      } else if (screen.current?.requestFullscreen) {
        await screen.current.requestFullscreen();
      } else {
        setPlaybackError("Full screen is unavailable in this browser.");
      }
    } catch {
      setPlaybackError("Full screen is unavailable in this browser.");
    }
  }

  return <div ref={screen} className="cinema-player" aria-label="Heritage film player">
    <div className={`cinema-picture ${orientation}`}>
      <video ref={video} playsInline preload="metadata" poster={poster} src={src}
        aria-label={`${orientation} film preview`}
        onClick={playPause}
        onLoadedMetadata={(event) => {
          const length = event.currentTarget.duration;
          if (Number.isFinite(length)) {
            setDuration(length);
            onDuration(length);
          }
        }}
        onTimeUpdate={(event) => setElapsed(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onVolumeChange={(event) => setMuted(event.currentTarget.muted)}
        onError={() => setPlaybackError("The film video could not be loaded.")} />
      {!playing && <button className="cinema-play" type="button" aria-label="Play film" onClick={() => {
        playPause();
        transportPlay.current?.focus();
      }}>
        <Play size={27} fill="currentColor" aria-hidden="true" />
      </button>}
    </div>
    <div className="cinema-controls" aria-label="Film playback controls">
      <input type="range" className="media-range cinema-seek" min={0} max={duration || 1} step={.1} value={elapsed}
        style={{ "--played": `${duration ? elapsed / duration * 100 : 0}%` } as CSSProperties}
        aria-label="Seek in the film" aria-valuetext={mediaTime(elapsed)} disabled={!duration}
        onChange={(event) => {
          if (video.current) {
            const seconds = Number(event.target.value);
            video.current.currentTime = seconds;
            setElapsed(seconds);
          }
        }} />
      <div className="cinema-toolbar">
        <div className="transport-buttons">
          <button ref={transportPlay} className="media-icon" type="button"
            aria-label={playing ? "Pause film" : "Play film from toolbar"} onClick={playPause}>
            {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
          </button>
          <button className="media-icon" type="button" aria-label="Back 10 seconds" disabled={!duration} onClick={() => skipMedia(video.current, -10)}><RotateCcw size={17} /></button>
          <span className="cinema-time"><strong>{mediaTime(elapsed)}</strong> / {mediaTime(duration)}</span>
        </div>
        <div className="transport-buttons">
          <span className="cinema-captions" title="Captions are included in the film"><Captions size={16} /><span>Captions included</span></span>
          <button className="media-icon" type="button" aria-label={muted ? "Unmute film" : "Mute film"}
            onClick={() => { if (video.current) video.current.muted = !muted; }}>{muted ? <VolumeX size={17} /> : <Volume2 size={17} />}</button>
          <button className="media-icon" type="button" aria-label={fullscreen ? "Exit full screen" : "View full screen"}
            onClick={() => void toggleFullscreen()}>{fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}</button>
        </div>
      </div>
      {playbackError && <p className="media-error" role="alert">{playbackError}</p>}
    </div>
  </div>;
}
