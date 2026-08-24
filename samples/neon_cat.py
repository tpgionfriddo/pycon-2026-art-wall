"""Neon Cat — animated. numpy glowing cat face: color-cycling rings, blinking eyes."""
import numpy as np

SIZE = 512
RINGS = 6            # neon contour rings between centre and outline
EAR_ANGLES = (55.0, 125.0)   # degrees, measured from +x counter-clockwise

_axis = np.linspace(-1.0, 1.0, SIZE)
X, Y = np.meshgrid(_axis, -_axis)          # y axis points up

# --- head silhouette: star-shaped outline with two ear spikes -------------
_dx, _dy = X - 0.0, Y - (-0.05)            # head centre
_r = np.hypot(_dx, _dy)
_theta = np.arctan2(_dy, _dx)

def _ear_bump(theta, center_deg, width=0.40, height=0.62):
    delta = np.abs(np.angle(np.exp(1j * (theta - np.deg2rad(center_deg)))))
    return height * np.clip(1.0 - delta / width, 0.0, 1.0)

_outline = 0.55 * (1.0 + sum(_ear_bump(_theta, a) for a in EAR_ANGLES))
D = _r / _outline                          # 0 at the centre, 1 on the outline
HEAD = np.clip((1.0 - D) / 0.015, 0.0, 1.0)   # anti-aliased silhouette alpha

# --- whiskers: soft glow around six line segments -------------------------
def _segment_glow(x0, y0, x1, y1, sigma=0.0045):
    px, py = X - x0, Y - y0
    vx, vy = x1 - x0, y1 - y0
    t = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0.0, 1.0)
    dist = np.hypot(px - t * vx, py - t * vy)
    return np.exp(-(dist / sigma) ** 2)

_WHISKER_ENDS = [((0.14, -0.16), (0.60, -0.06)),
                 ((0.14, -0.19), (0.62, -0.19)),
                 ((0.13, -0.22), (0.58, -0.32))]
WHISKERS = np.zeros((SIZE, SIZE))
for (x0, y0), (x1, y1) in _WHISKER_ENDS:
    WHISKERS += _segment_glow(x0, y0, x1, y1)      # right side
    WHISKERS += _segment_glow(-x0, y0, -x1, y1)    # mirrored left side
WHISKERS = np.clip(WHISKERS, 0.0, 1.0)

# --- eyes and nose (geometry only; openness is animated in draw) ----------
EYE_W, EYE_H = 0.130, 0.080
PUPIL_W, PUPIL_H = 0.030, 0.068
EYES = [(X - sx * 0.22, Y - 0.06) for sx in (-1, 1)]

_nx, _ny = X, Y - (-0.155)                 # nose top edge
NOSE = (_ny <= 0.0) & (_ny >= -0.07) & (np.abs(_nx) <= 0.055 * (1.0 + _ny / 0.07))

EYE_COLOR = np.array([0.72, 1.00, 0.38])
PUPIL_COLOR = np.array([0.02, 0.05, 0.06])
NOSE_COLOR = np.array([1.00, 0.45, 0.62])
WHISKER_COLOR = np.array([0.95, 0.98, 1.00])


def draw(t):
    t = t % 1.0                            # frame at t=1.0 == frame at t=0.0
    # neon rings marching outward; the -2*pi*t phase makes a perfect loop
    phase = 2.0 * np.pi * (RINGS * D + 0.08 * np.sin(7.0 * _theta) - t)
    rings = 0.25 + 0.75 * (0.5 + 0.5 * np.sin(phase)) ** 3

    # slowly rotating neon palette (one full hue cycle per loop)
    hue = 2.0 * np.pi * (0.9 * D - t)
    rgb = np.stack([0.5 + 0.5 * np.sin(hue),
                    0.5 + 0.5 * np.sin(hue + 2.0 * np.pi / 3.0),
                    0.5 + 0.5 * np.sin(hue + 4.0 * np.pi / 3.0)], axis=-1)
    rgb *= rings[..., None]

    # one quick blink per loop, centred at t = 0.5 (exactly periodic)
    openness = 1.0 - np.exp(30.0 * (np.cos(2.0 * np.pi * (t - 0.5)) - 1.0))
    openness = max(openness, 1e-3)

    for ex, ey in EYES:
        eye = (ex / EYE_W) ** 2 + (ey / (EYE_H * openness)) ** 2
        mask = eye <= 1.0
        glow = np.clip(1.0 - eye, 0.0, 1.0)[..., None]
        rgb = np.where(mask[..., None], EYE_COLOR * (0.45 + 0.55 * glow), rgb)
        pupil = (ex / PUPIL_W) ** 2 + (ey / (PUPIL_H * openness)) ** 2 <= 1.0
        rgb = np.where(pupil[..., None], PUPIL_COLOR, rgb)

    rgb = np.where(NOSE[..., None], NOSE_COLOR, rgb)

    w = (0.9 * WHISKERS)[..., None]
    rgb = rgb * (1.0 - w) + WHISKER_COLOR * w

    alpha = np.maximum(HEAD, WHISKERS)     # whiskers stick out past the head
    return np.dstack([np.clip(rgb, 0.0, 1.0), alpha])
