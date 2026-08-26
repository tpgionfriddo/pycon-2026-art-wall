"""Unfolding spectrum. Animated, drawn straight into a numpy array."""
import numpy as np

_SIZE = 512
_Y, _X = np.mgrid[0:_SIZE, 0:_SIZE].astype(np.float32)
_CX = _CY = (_SIZE - 1) * 0.5

_STOPS = np.array([0.0, 0.33, 0.7227778, 1.0], dtype=np.float32)
_RED = np.array([255, 72, 167, 241], dtype=np.float32)
_GREEN = np.array([255, 93, 90, 65], dtype=np.float32)
_BLUE = np.array([255, 169, 171, 115], dtype=np.float32)

_COUNT = 9
_INDEX = np.arange(_COUNT, dtype=np.float32)
_BASE_ANGLE = 2.0 * np.pi * _INDEX / _COUNT - np.pi * 0.5
_BASE_LENGTH = 228.0 + 34.0 * np.sin(_INDEX * 1.73)
_BASE_WIDTH = 22.0 + 9.0 * (0.5 + 0.5 * np.sin(_INDEX * 2.41))
_COLOR_POS = ((_INDEX / _COUNT) + 0.08) % 1.0
_BRUSH_COLORS = np.stack(
    [
        np.interp(_COLOR_POS, _STOPS, _RED),
        np.interp(_COLOR_POS, _STOPS, _GREEN),
        np.interp(_COLOR_POS, _STOPS, _BLUE),
    ],
    axis=1,
).astype(np.float32)


def draw(t):
    t = t % 1.0
    phase = 2.0 * np.pi * t

    premultiplied = np.zeros((_SIZE, _SIZE, 3), dtype=np.float32)
    alpha = np.zeros((_SIZE, _SIZE), dtype=np.float32)

    pivot_x = _CX + 7.0 * np.sin(phase)
    pivot_y = _CY + 7.0 * np.cos(phase)
    px = _X - pivot_x
    py = _Y - pivot_y

    for i in range(_COUNT):
        ripple = np.sin(phase + i * 0.61)
        angle = _BASE_ANGLE[i] + 0.26 * np.sin(phase + i * 0.19)
        length = _BASE_LENGTH[i] + 42.0 * ripple
        width = _BASE_WIDTH[i] + 5.0 * np.sin(phase * 2.0 + i * 0.83)
        corner = min(width * 0.46, 15.0)

        ca = np.cos(angle)
        sa = np.sin(angle)
        along = px * ca + py * sa
        across = -px * sa + py * ca

        qx = np.abs(along - length * 0.5) - (length * 0.5 - corner)
        qy = np.abs(across) - (width * 0.5 - corner)
        distance = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - corner
        mask = np.clip(1.0 - distance, 0.0, 1.0)

        color = _BRUSH_COLORS[i]
        premultiplied = color[None, None, :] * mask[..., None] + premultiplied * (1.0 - mask[..., None])
        alpha = mask + alpha * (1.0 - mask)

    highlight = np.exp(-((_X - pivot_x) ** 2 + (_Y - pivot_y) ** 2) / 1050.0) * 0.24
    premultiplied = 255.0 * highlight[..., None] + premultiplied * (1.0 - highlight[..., None])
    alpha = highlight + alpha * (1.0 - highlight)

    result = np.empty((_SIZE, _SIZE, 4), dtype=np.uint8)
    result[..., :3] = np.clip(premultiplied / np.maximum(alpha[..., None], 1e-6), 0, 255).astype(np.uint8)
    result[..., 3] = np.round(alpha * 255).astype(np.uint8)
    return result
