"""Plasma shader — animated. Pure numpy, loops perfectly."""
import numpy as np

SIZE = 512

def draw(t):
    a = 2 * np.pi * t  # one full cycle over the loop
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE * 4.0 - 2.0

    v = (
        np.sin(3.0 * x + a)
        + np.sin(3.0 * (x * np.cos(a) + y * np.sin(a)))
        + np.sin(4.0 * np.hypot(x, y) - 2.0 * a)
    )

    r = 0.5 + 0.5 * np.sin(np.pi * v)
    g = 0.5 + 0.5 * np.sin(np.pi * v + 2.094)
    b = 0.5 + 0.5 * np.sin(np.pi * v + 4.189)
    return (np.dstack([r, g, b]) * 255).astype(np.uint8)