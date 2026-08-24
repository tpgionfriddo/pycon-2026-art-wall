"""Render harness — runs INSIDE the sandbox container, never on the host.

Usage: python render_job.py /job/submission.py /out

Executes the submission's draw()/draw(t), writes the piece media plus a
result.json into /out. Output spec (MVP plan §3):
  static   -> piece.png, downscaled to fit 1024x1024
  animated -> piece.webm, 150 frames @ 30 fps (5 s loop), fit 512x512,
              encoded by the in-container ffmpeg to WebM/VP9 (ADR-0003)
Aspect ratio is always preserved (fit-in-box, no crop/stretch).
Alpha is preserved end-to-end: PNGs keep the full alpha channel and WebM
is encoded with VP9 alpha (yuva420p), so transparent backgrounds survive.
"""
import importlib.util
import inspect
import json
import subprocess
import sys
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from preview import normalize  # reused verbatim from samples/preview.py

FRAMES, FPS = 150, 30
STATIC_BOX, VIDEO_BOX = 1024, 512


def load_draw(src: Path):
    spec = importlib.util.spec_from_file_location("submission", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    draw = getattr(mod, "draw", None)
    if not callable(draw):
        raise RuntimeError("submission must define draw() or draw(t)")
    n_params = len(inspect.signature(draw).parameters)
    if n_params > 1:
        raise RuntimeError("draw must take 0 or 1 parameters")
    return draw, n_params


def fit_in_box(img, box: int):
    """Downscale to fit box×box, preserving aspect ratio; never upscale."""
    if img.width > box or img.height > box:
        img = img.copy()
        img.thumbnail((box, box))
    return img


def render_static(draw, out_dir: Path) -> str:
    img = fit_in_box(normalize(draw()), STATIC_BOX)
    img.save(out_dir / "piece.png")
    return "piece.png"


def render_animated(draw, out_dir: Path) -> str:
    first = fit_in_box(normalize(draw(0.0)), VIDEO_BOX)
    # yuva420p requires even dimensions; lock every frame to this geometry
    w, h = max(2, first.width // 2 * 2), max(2, first.height // 2 * 2)
    out = out_dir / "piece.webm"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34",
        "-deadline", "good", "-cpu-used", "5", "-row-mt", "1",
        "-pix_fmt", "yuva420p", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(FRAMES):
            frame = fit_in_box(normalize(draw(i / FRAMES)), VIDEO_BOX)
            if (frame.width, frame.height) != (w, h):
                frame = frame.resize((w, h))
            proc.stdin.write(
                np.asarray(frame.convert("RGBA"), dtype=np.uint8).tobytes())
    finally:
        proc.stdin.close()
        returncode = proc.wait()
    if returncode != 0:
        raise RuntimeError(f"ffmpeg exited with code {returncode}")
    return "piece.webm"


def main() -> None:
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    result = {"kind": None, "media": None, "error": None}
    try:
        draw, n_params = load_draw(src)
        result["kind"] = "static" if n_params == 0 else "animated"
        render = render_static if n_params == 0 else render_animated
        result["media"] = render(draw, out_dir)
    except Exception:
        result["error"] = traceback.format_exc(limit=8)
    (out_dir / "result.json").write_text(json.dumps(result))


if __name__ == "__main__":
    main()
