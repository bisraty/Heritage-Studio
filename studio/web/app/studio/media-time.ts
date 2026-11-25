export function mediaTime(seconds: number) {
  const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function skipMedia(player: HTMLMediaElement | null, seconds: number) {
  if (player && Number.isFinite(player.duration)) {
    player.currentTime = Math.max(0, Math.min(player.duration, player.currentTime + seconds));
  }
}
