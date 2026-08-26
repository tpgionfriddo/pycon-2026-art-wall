"""A still image. Static numpy, concentric rings."""
# draw() takes no argument, so this piece is a still image.
#
# It returns a numpy array shaped (height, width, 4): red, green, blue and
# alpha. Alpha is transparency, and setting it to 0 outside the circle is
# what gives the piece see-through corners on the wall.

import numpy as np

SIZE = 512
RINGS = 9

# One flat colour per ring, cycled. No blending between them, so every edge
# in the image is a hard one.
PALETTE = np.array([
    [0.99, 0.50, 0.11],
    [1.00, 0.19, 0.55],
    [0.42, 0.34, 1.00],
    [0.05, 0.05, 0.09],
])


def draw():
    # x and y each run 0 to 1 across the image, so this is every pixel's
    # position rather than a loop over them.
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE

    # Distance from the middle: 0 at the centre, 1 at the edge of the disc.
    radius = np.hypot(x - 0.5, y - 0.5) * 2

    # Which ring each pixel falls in, and therefore which colour it takes.
    ring = np.floor(np.clip(radius, 0, 1) * RINGS).astype(int)

    rgba = np.zeros((SIZE, SIZE, 4))
    rgba[..., :3] = PALETTE[ring % len(PALETTE)]
    rgba[..., 3] = radius <= 1.0
    return rgba
