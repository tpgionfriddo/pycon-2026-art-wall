"""Stick Dance — animated. numpy stick figure dancing over a "Hello world!" box."""
import numpy as np

SIZE = 512

_axis = np.arange(SIZE, dtype=np.float32)
X, Y = np.meshgrid(_axis, _axis)           # pixel coords, y grows downward

# --- tiny 5x7 pixel font (only the glyphs "Hello world!" needs) -----------
_GLYPHS = {
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "e": ["00000", "00000", "01110", "10001", "11111", "10000", "01110"],
    "l": ["01100", "00100", "00100", "00100", "00100", "00100", "01110"],
    "o": ["00000", "00000", "01110", "10001", "10001", "10001", "01110"],
    "w": ["00000", "00000", "10001", "10001", "10101", "10101", "01010"],
    "r": ["00000", "00000", "10110", "11001", "10000", "10000", "10000"],
    "d": ["00001", "00001", "01101", "10011", "10001", "10011", "01101"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}

def _text_bitmap(text):
    cols = [np.array([[int(c) for c in row] for row in _GLYPHS[ch]], np.float32)
            for ch in text]
    gap = np.zeros((7, 1), np.float32)
    out = cols[0]
    for col in cols[1:]:
        out = np.hstack([out, gap, col])
    return out

_TEXT_SCALE = 4
_text = np.kron(_text_bitmap("Hello world!"), np.ones((_TEXT_SCALE, _TEXT_SCALE), np.float32))
_TH, _TW = _text.shape                     # 28 x 284

# --- speech-box geometry (static, precomputed) -----------------------------
BOX_CX, BOX_CY = 256.0, 428.0
BOX_W, BOX_H, BOX_R = 340.0, 76.0, 16.0

_qx = np.abs(X - BOX_CX) - (BOX_W * 0.5 - BOX_R)
_qy = np.abs(Y - BOX_CY) - (BOX_H * 0.5 - BOX_R)
_box_d = (np.hypot(np.maximum(_qx, 0), np.maximum(_qy, 0))
          + np.minimum(np.maximum(_qx, _qy), 0) - BOX_R)
BOX_FILL = np.clip(0.5 - _box_d, 0.0, 1.0)
BOX_BORDER = np.clip(2.5 - np.abs(_box_d), 0.0, 1.0)

TEXT = np.zeros((SIZE, SIZE), np.float32)
_ty, _tx = int(BOX_CY - _TH / 2), int(BOX_CX - _TW / 2)
TEXT[_ty:_ty + _TH, _tx:_tx + _TW] = _text

BOX_COLOR = np.array([0.10, 0.12, 0.18], np.float32)
TEXT_COLOR = np.array([1.00, 0.95, 0.70], np.float32)
FIGURE_COLOR = np.array([0.98, 0.97, 0.94], np.float32)

LIMB_W = 5.0                               # half-thickness of a stroke, px


def _stroke(mask, x0, y0, x1, y1, w=LIMB_W):
    """Accumulate an anti-aliased thick line segment into mask (in place)."""
    px, py = X - x0, Y - y0
    vx, vy = x1 - x0, y1 - y0
    tt = np.clip((px * vx + py * vy) / max(vx * vx + vy * vy, 1e-6), 0.0, 1.0)
    dist = np.hypot(px - tt * vx, py - tt * vy)
    np.maximum(mask, np.clip(w + 0.5 - dist, 0.0, 1.0), out=mask)


def _pose(t):
    """Joint positions for the dance; every term loops perfectly over t in [0,1)."""
    p = 2.0 * np.pi * t
    beat = np.sin(2.0 * p)                 # two beats per loop
    bounce = np.abs(beat)                  # body bob on every beat

    hip = np.array([256.0 + 30.0 * beat, 252.0 - 14.0 * bounce])
    lean = 0.22 * beat
    up = np.array([np.sin(lean), -np.cos(lean)])
    neck = hip + 88.0 * up
    head = neck + 26.0 * up

    joints = {"hip": hip, "neck": neck, "head": head}

    # arms: "raise the roof" — forearms pump up and down in alternation
    for side, sx, ph in (("l", -1.0, 0.0), ("r", 1.0, np.pi)):
        ua = 0.45 + 0.25 * np.sin(2.0 * p + ph)          # upper-arm lift
        elbow = neck + 52.0 * np.array([sx * np.cos(ua), -np.sin(ua)])
        fa = 1.15 + 0.65 * np.sin(2.0 * p + ph)          # forearm wave
        hand = elbow + 48.0 * np.array([sx * np.cos(fa), -np.sin(fa)])
        joints["elbow_" + side] = elbow
        joints["hand_" + side] = hand

    # legs: alternating side-steps with a little knee lift
    for side, sx, ph in (("l", -1.0, 0.0), ("r", 1.0, np.pi)):
        lift = np.maximum(0.0, np.sin(2.0 * p + ph))     # this leg's step
        th = 0.20 * np.sin(2.0 * p + ph) + sx * 0.16     # thigh swing
        knee = hip + 62.0 * np.array([np.sin(th), np.cos(th)])
        sh = th - 0.55 * lift                            # shin folds on lift
        foot = knee + 58.0 * np.array([np.sin(sh), np.cos(sh)])
        joints["knee_" + side] = knee
        joints["foot_" + side] = foot

    return joints


def draw(t):
    t = t % 1.0                            # frame at t=1.0 == frame at t=0.0
    j = _pose(t)

    figure = np.zeros((SIZE, SIZE), np.float32)
    _stroke(figure, *j["hip"], *j["neck"])                     # spine
    for side in ("l", "r"):
        _stroke(figure, *j["neck"], *j["elbow_" + side])       # upper arms
        _stroke(figure, *j["elbow_" + side], *j["hand_" + side])
        _stroke(figure, *j["hip"], *j["knee_" + side])         # legs
        _stroke(figure, *j["knee_" + side], *j["foot_" + side])

    hx, hy = j["head"]
    head_d = np.hypot(X - hx, Y - hy)
    np.maximum(figure, np.clip(20.0 + 0.5 - head_d, 0.0, 1.0), out=figure)

    # border hue makes one full cycle per loop, so the animation loops exactly
    hue = 2.0 * np.pi * t
    border = np.array([0.5 + 0.5 * np.sin(hue),
                       0.5 + 0.5 * np.sin(hue + 2.0 * np.pi / 3.0),
                       0.5 + 0.5 * np.sin(hue + 4.0 * np.pi / 3.0)], np.float32)
    border = 0.35 + 0.65 * border

    rgb = np.zeros((SIZE, SIZE, 3), np.float32)
    alpha = np.zeros((SIZE, SIZE), np.float32)
    for mask, color in ((BOX_FILL, BOX_COLOR), (BOX_BORDER, border),
                        (TEXT, TEXT_COLOR), (figure, FIGURE_COLOR)):
        m = mask[..., None]
        rgb = color * m + rgb * (1.0 - m)
        alpha = mask + alpha * (1.0 - mask)

    return np.dstack([np.clip(rgb, 0.0, 1.0), alpha])
