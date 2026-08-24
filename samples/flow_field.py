"""Flow field trails — static. numpy + matplotlib."""
import numpy as np
import matplotlib.pyplot as plt

def field(p):
    x, y = p[:, 0], p[:, 1]
    a = np.sin(1.7 * y + np.cos(2.3 * x)) + 0.5 * np.cos(1.3 * x - 0.7 * y)
    return np.column_stack([np.cos(a * np.pi), np.sin(a * np.pi)])

def draw():
    rng = np.random.default_rng(42)
    pts = rng.uniform(-2, 2, (900, 2))

    trails = [pts.copy()]
    for _ in range(70):
        pts = pts + 0.02 * field(pts)
        trails.append(pts.copy())
    trails = np.array(trails)  # (steps, n, 2)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=100)
    fig.patch.set_facecolor("none")   # transparent background
    ax.set_facecolor("none")

    colors = plt.cm.plasma(np.linspace(0, 1, trails.shape[1]))
    for i in range(trails.shape[1]):
        ax.plot(trails[:, i, 0], trails[:, i, 1],
                color=colors[i], lw=0.6, alpha=0.65)

    ax.set_xlim(-2, 2), ax.set_ylim(-2, 2)
    ax.set_aspect("equal"), ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return fig