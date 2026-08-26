"""A plot as art. Static matplotlib, returning the Figure."""
# draw() can hand back a matplotlib Figure instead of an array, so anything
# you know how to plot is already a piece.
#
# The axes, ticks and frame are switched off and the background is left
# transparent, so the curve is the whole image.

import numpy as np
import matplotlib.pyplot as plt

POINTS = 2000
PETALS = 5


def draw():
    angle = np.linspace(0, 2 * np.pi, POINTS)

    # A rose curve. cos(5 * angle) gives five petals; try 4 or 7 and preview
    # again to see what changes.
    radius = np.cos(PETALS * angle)
    x, y = radius * np.cos(angle), radius * np.sin(angle)

    fig, ax = plt.subplots(figsize=(5.12, 5.12), dpi=100)
    fig.patch.set_facecolor("none")   # transparent background
    ax.set_facecolor("none")
    ax.plot(x, y, color="#6B57FF", linewidth=2.5)
    ax.scatter(x[::40], y[::40], s=16, color="#FF318C", zorder=3)
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    return fig
