"""Aquion logo afloat. Animated, Bezier logo geometry over a numpy water
surface."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D

SIZE = 512
NAVY, ORANGE = "#020763", "#ff7b00"

# --- Logo geometry, in the mark's own 196x151 unit box (y grows downwards) ---
# Each flank of the arch is two cubic Beziers fitted to the original outline.
# Every fit lands within 0.7 units of it, so the silhouette is the real one.
APEX = (96.5, -1.5)
VOID_APEX = (100.5, 33.8)                                  # tip of the counter
OUTER_L = [APEX, (80.2, 4.7), (74.2, 21.8), (67.0, 36.0),
           (52.1, 72.3), (42.3, 110.4), (27.5, 147.0)]
INNER_L = [(96.0, 36.0), (82.5, 41.8), (76.1, 55.6), (70.0, 68.0),
           (54.9, 93.9), (42.9, 121.4), (27.5, 147.0)]
OUTER_R = [APEX, (111.0, 4.7), (119.4, 18.5), (126.0, 32.0),
           (139.5, 59.6), (150.7, 87.9), (163.0, 116.0)]
INNER_R = [(104.5, 36.0), (117.7, 40.2), (123.0, 53.5), (130.0, 64.0),
           (142.5, 80.4), (151.8, 98.7), (163.0, 116.0)]

# The swoosh is an arc of a single rotated ellipse, found by an orthogonal-
# distance fit to the original stroke's medial line (rms 1.1 units; it runs
# ~4 wide of the hook's very tip, where the real swash curls tighter than any
# ellipse can). SW_W is the stroke width measured at the listed angles.
SW_C, SW_RX, SW_RY, SW_ROT = (111.4, 43.1), 40.4, 112.3, 65.9
SW_T = [-35.5, -24, -12, 0, 12, 24, 36, 48, 58, 68, 78, 88, 98, 108, 114]
SW_W = [1.0, 1.8, 2.6, 3.8, 5.3, 6.6, 8.0, 8.6, 9.0, 8.3, 6.3, 4.4, 3.0, 1.6, 1.0]
WEAVE_X = 112.0            # swoosh crosses over the right flank, under the left

# Wordmark: the cap band, and the x-span each letter fills in the original.
# DejaVu Sans is the only face the sandbox ships; the original is a little
# narrower, so squeeze every glyph by the same least-squares factor.
WORD_TOP, WORD_BASE, CONDENSE = 120.8, 144.8, 0.86
WORDMARK = [("A", 46, 64), ("Q", 72, 92), ("U", 99, 115),
            ("I", 126, 130), ("O", 139, 159), ("N", 168, 185)]

# --- Layout: where the mark sits on the canvas, and where the water starts ---
SCALE = 384 / 196.0                  # logo units -> canvas px
OX, OY = (SIZE - 384) / 2, 54.0      # canvas px of logo unit (0, 0)
WATERLINE = 372                      # canvas row of the surface
SQUASH = 0.44                        # reflection foreshortening
N_BUBBLES = 30

SKY_TOP, SKY_BOT = (0.949, 0.980, 0.992), (0.855, 0.933, 0.961)
SEA_TOP, SEA_BOT = (0.780, 0.898, 0.937), (0.612, 0.804, 0.878)


def _arch_path():
    """The A as one closed outline: down a flank, up its counter, and round."""
    verts, codes = [APEX], [Path.MOVETO]
    verts += OUTER_R[1:]; codes += [Path.CURVE4] * 6       # down the right flank
    verts += INNER_R[-2::-1]; codes += [Path.CURVE4] * 6   # up the counter's right
    verts += [VOID_APEX, INNER_L[0]]; codes += [Path.CURVE3] * 2
    verts += INNER_L[1:]; codes += [Path.CURVE4] * 6       # down the counter's left
    verts += OUTER_L[-2::-1]; codes += [Path.CURVE4] * 6   # up the left flank
    verts += [APEX]; codes += [Path.CLOSEPOLY]
    return Path(verts, codes)


def _swoosh_polygon(n=320):
    """Offset the ellipse arc by +-half its measured width along the normal."""
    t = np.radians(np.linspace(SW_T[0], SW_T[-1], n))
    c, s = np.cos(np.radians(SW_ROT)), np.sin(np.radians(SW_ROT))

    ex, ey = SW_RX * np.cos(t), SW_RY * np.sin(t)          # centreline, unrotated
    px = SW_C[0] + ex * c - ey * s
    py = SW_C[1] + ex * s + ey * c

    dx, dy = -SW_RX * np.sin(t), SW_RY * np.cos(t)         # tangent, unrotated
    tx, ty = dx * c - dy * s, dx * s + dy * c
    norm = np.hypot(tx, ty)
    nx, ny = -ty / norm, tx / norm

    half = np.interp(np.degrees(t), SW_T, SW_W) / 2
    outer = np.column_stack([px + nx * half, py + ny * half])
    inner = np.column_stack([px - nx * half, py - ny * half])
    return np.vstack([outer, inner[::-1]])


def _wordmark_patches(transform):
    """Glyphs scaled off a shared cap height and centred on their own spans."""
    font = FontProperties(family="DejaVu Sans", weight="bold")
    glyphs = {c: TextPath((0, 0), c, size=100, prop=font) for c, _, _ in WORDMARK}
    k = (WORD_BASE - WORD_TOP) / glyphs["A"].get_extents().height  # 'A' has no tail

    for char, x0, x1 in WORDMARK:
        tp = glyphs[char]
        bb = tp.get_extents()
        fit = (Affine2D()
               .translate(-bb.x0 - bb.width / 2, 0)        # origin at baseline mid
               .scale(k * CONDENSE, -k)                    # flip: logo y grows down
               .translate((x0 + x1) / 2, WORD_BASE))
        yield PathPatch(tp, transform=fit + transform, fc=NAVY, lw=0)


def _logo_layer():
    """Render the mark once, as a float RGBA layer the size of the canvas."""
    fig, ax = plt.subplots(figsize=(SIZE / 100, SIZE / 100), dpi=100)
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")
    ax.set_xlim(0, SIZE), ax.set_ylim(SIZE, 0)             # canvas px, y down
    ax.set_position([0, 0, 1, 1]), ax.axis("off")

    trans = Affine2D().scale(SCALE, SCALE).translate(OX, OY) + ax.transData
    arch = _arch_path()
    ax.add_patch(PathPatch(arch, transform=trans, fc=NAVY, lw=0))
    ax.add_patch(Polygon(_swoosh_polygon(), transform=trans, fc=ORANGE, lw=0))

    # Re-lay the left flank over the swoosh, which makes the two interlace.
    over = PathPatch(arch, transform=trans, fc=NAVY, lw=0)
    ax.add_patch(over)
    over.set_clip_path(Path([(-20, -20), (WEAVE_X, -20), (WEAVE_X, 200),
                             (-20, 200), (-20, -20)]), trans)

    for patch in _wordmark_patches(trans):
        ax.add_patch(patch)

    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba(), dtype=np.float64) / 255.0
    plt.close(fig)
    return rgba


LOGO = _logo_layer()          # the geometry never moves, so build it once


def _water(a):
    """Sky-over-sea gradient lit by two looping caustic wave trains."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    depth = np.clip((np.arange(SIZE) - WATERLINE) / (SIZE - WATERLINE), 0, 1)

    def ramp(top, bot, u):
        return np.dstack([c0 + (c1 - c0) * u for c0, c1 in zip(top, bot)])

    sky = ramp(SKY_TOP, SKY_BOT, np.clip(yy * SIZE / WATERLINE, 0, 1))
    sea = ramp(SEA_TOP, SEA_BOT, depth[:, None] * np.ones(SIZE))
    rgb = np.where((np.arange(SIZE) >= WATERLINE)[:, None, None], sea, sky)

    # A radial swell plus a diagonal train. Both phases are whole multiples of
    # the loop, so the surface comes back to itself exactly at t = 1.
    ring = np.hypot(xx - 0.5, yy - 1.28)
    caustic = np.sin(34 * ring - 2 * a) + 0.6 * np.sin(21 * (0.7 * xx + yy) + a)
    rgb = rgb + 0.035 * (caustic * depth[:, None])[..., None]

    edge = (np.arange(SIZE) - WATERLINE)[:, None, None]
    ripple = 0.75 + 0.25 * np.sin(30 * xx[:1, :, None] + a)     # break up the line
    glint = (0.24 * np.exp(-((edge / 2.4) ** 2)) * ripple
             + 0.09 * np.exp(-((edge / 15.0) ** 2)))
    return np.clip(rgb + glint, 0, 1)


def _bubbles(rgb, a):
    """Ion bubbles rising through the water; integer speeds keep the loop shut."""
    rng = np.random.default_rng(11)
    for i in range(N_BUBBLES):
        x0, r = rng.uniform(0.04, 0.96), rng.uniform(1.6, 5.0)
        rise, sway = rng.integers(1, 3), rng.integers(1, 3)
        u = (rng.random() + rise * a / (2 * np.pi)) % 1.0   # 1 deep, 0 at surface
        cy = SIZE - u * (SIZE - WATERLINE + 6)
        cx = x0 * SIZE + 5 * np.sin(2 * np.pi * (sway * a / (2 * np.pi) + x0))
        tint = ORANGE if i % 5 == 0 else "#ffffff"
        col = np.array([int(tint[j:j + 2], 16) / 255 for j in (1, 3, 5)])

        pad = int(r) + 2
        y0, y1 = max(int(cy) - pad, 0), min(int(cy) + pad + 1, SIZE)
        xa, xb = max(int(cx) - pad, 0), min(int(cx) + pad + 1, SIZE)
        if y0 >= y1 or xa >= xb:
            continue
        gy, gx = np.mgrid[y0:y1, xa:xb]
        soft = np.clip(r - np.hypot(gx - cx, gy - cy), 0, 1)
        alpha = (0.5 * soft * min(u * 4, 1.0))[..., None]   # fade in from depth
        rgb[y0:y1, xa:xb] = rgb[y0:y1, xa:xb] * (1 - alpha) + col * alpha
    return rgb


def _reflection(rgb, a):
    """Mirror the mark below the surface, shearing each row on a looping wave."""
    below = np.arange(WATERLINE, SIZE) - WATERLINE
    src = WATERLINE - below / SQUASH                        # foreshortened mirror
    shift = (1.5 + 0.10 * below) * np.sin(below / 11.0 - 3 * a)

    cols = np.arange(SIZE)
    sx = np.clip(np.rint(cols[None, :] - shift[:, None]), 0, SIZE - 1).astype(int)
    sy = np.clip(np.rint(src), 0, SIZE - 1).astype(int)[:, None]

    sample = LOGO[sy, sx]
    alpha = (sample[..., 3] * (0.42 * np.exp(-below / 78.0))[:, None])[..., None]
    band = rgb[WATERLINE:]
    rgb[WATERLINE:] = band * (1 - alpha) + sample[..., :3] * alpha
    return rgb


def draw(t):
    a = 2 * np.pi * t
    rgb = _reflection(_bubbles(_water(a), a), a)

    alpha = LOGO[..., 3:]                                   # crisp mark on top
    rgb = rgb * (1 - alpha) + LOGO[..., :3] * alpha
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
