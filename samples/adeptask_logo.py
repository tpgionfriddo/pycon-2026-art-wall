"""Adeptask logo — static. numpy conic-gradient rounded square."""
import numpy as np

SIZE = 1024
MARGIN = 0.06        # fraction of the canvas half-width left empty around the square
CORNER_FRAC = 0.22   # corner radius as a fraction of the square's half-side

# Angle positions mirror CSS conic-gradient()'s rule for an omitted stop
# position: it's placed halfway between its neighboring explicit stops.
STOPS = [
    (0.0, np.array([255, 255, 255], dtype=np.float64)),
    (130.1, np.array([72, 93, 169], dtype=np.float64)),
    (260.2, np.array([167, 90, 171], dtype=np.float64)),
    (360.0, np.array([241, 65, 115], dtype=np.float64)),
]

def _gradient_colors(angles):
    colors = np.empty(angles.shape + (3,), dtype=np.float64)
    for (a0, c0), (a1, c1) in zip(STOPS, STOPS[1:]):
        mask = (angles >= a0) & (angles <= a1)
        frac = (angles - a0) / (a1 - a0)
        colors[mask] = c0 + (c1 - c0) * frac[mask][:, None]
    return colors

def draw():
    half = SIZE / 2
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    dx, dy = x - half, y - half

    # Clockwise angle from straight up, matching CSS conic-gradient's default.
    angles = np.degrees(np.arctan2(dx, -dy)) % 360.0
    rgb = _gradient_colors(angles)

    side_half = half * (1 - MARGIN)
    radius = side_half * CORNER_FRAC
    qx = np.abs(dx) - (side_half - radius)
    qy = np.abs(dy) - (side_half - radius)
    dist = (np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
            + np.minimum(np.maximum(qx, qy), 0) - radius)

    alpha = np.clip(1.0 - dist, 0, 1) * 255  # ~1px anti-aliased rounded edge

    return np.dstack([rgb, alpha]).astype(np.uint8)
