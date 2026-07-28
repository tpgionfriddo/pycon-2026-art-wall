# Animated pieces are encoded to WebM (VP9) inside the render container

Animated pieces are encoded by ffmpeg inside the render container (the image
ships ffmpeg; frames never leave the sandbox unencoded). We chose WebM/VP9
over MP4/H.264 for its royalty-free codec and better quality-per-bitrate,
accepting a known risk: TV/mini-PC browsers without VP9 hardware decoding may
stutter with ~50 simultaneous video tiles.

## Consequences

- **Blocking acceptance item:** a 50-tile playback smoke test on the actual
  booth wall hardware must pass before the event.
- Fallback is H.264/MP4 — a one-line ffmpeg change in the worker; only
  already-rendered pieces would need re-encoding.
