# Your piece goes here.
#
# draw(t) makes an animated piece: t sweeps 0 to 1
# over one 5-second loop. Drop the t for a still image.
#
# New to this? Pick something from "Load an example"
# above, press Preview, and read the code.

import numpy as np

SIZE = 512

def draw(t):
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    blue = 0.5 + 0.5 * np.sin(2 * np.pi * t)
    return np.dstack([x, y, np.full_like(x, blue)])
