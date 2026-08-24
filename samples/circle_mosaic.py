"""Circle-intersection mosaic — static. shapely + colour + matplotlib."""
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from shapely.ops import unary_union, polygonize
from colour import Color

def draw():
    rng = np.random.default_rng(7)
    circles = [
        Point(rng.uniform(-1, 1), rng.uniform(-1, 1)).buffer(
            rng.uniform(0.25, 0.7), quad_segs=64)
        for _ in range(14)
    ]

    # Node all circle boundaries together, then extract every enclosed region
    regions = list(polygonize(unary_union([c.boundary for c in circles])))

    palette = [c.hex_l for c in
               Color("#12c2e9").range_to(Color("#f64f59"), len(regions))]
    order = np.argsort([r.centroid.x + r.centroid.y for r in regions])

    fig, ax = plt.subplots(figsize=(6, 6), dpi=100)
    fig.patch.set_facecolor("none")   # transparent background
    ax.set_facecolor("none")

    for rank, idx in enumerate(order):
        ax.fill(*regions[idx].exterior.xy, color=palette[rank],
                lw=0.5, ec="#101018")

    ax.set_aspect("equal"), ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return fig