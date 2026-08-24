"""Render a draw()/draw(t) submission to PNG or looping GIF.

Usage: uv run python samples/preview.py samples/plasma_shader.py
"""
import importlib.util
import inspect
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # must happen before samples import pyplot

import numpy as np
from PIL import Image

FRAMES, FPS = 150, 30

def normalize(obj) -> Image.Image:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    if isinstance(obj, Figure):
        obj.canvas.draw()
        arr = np.asarray(obj.canvas.buffer_rgba()).copy()
        plt.close(obj)
        return Image.fromarray(arr)
    if isinstance(obj, Image.Image):
        return obj.convert("RGBA")
    arr = np.asarray(obj)
    if arr.dtype != np.uint8:
        arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.dstack([arr] * 3)
    if arr.shape[-1] == 3:  # RGB -> opaque RGBA
        arr = np.dstack([arr, np.full(arr.shape[:2], 255, np.uint8)])
    return Image.fromarray(arr)

def gif_frame(img: Image.Image) -> Image.Image:
    """Palette frame with 1-bit transparency (all GIF can express)."""
    alpha = img.getchannel("A")
    frame = img.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
    frame.paste(255, Image.eval(alpha, lambda a: 255 if a < 128 else 0))
    frame.info["transparency"] = 255
    return frame

def main():
    src = Path(sys.argv[1])
    spec = importlib.util.spec_from_file_location(src.stem, src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    draw = mod.draw
    if len(inspect.signature(draw).parameters) == 0:
        out = src.with_suffix(".png")
        normalize(draw()).save(out)
    else:
        out = src.with_suffix(".gif")
        frames = [gif_frame(normalize(draw(i / FRAMES))) for i in range(FRAMES)]
        frames[0].save(out, save_all=True, append_images=frames[1:],
                       duration=1000 // FPS, loop=0,
                       transparency=255, disposal=2)
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
