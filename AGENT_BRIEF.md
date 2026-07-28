# Agent Brief: Conference "Code Art Wall"

## Context

We are exhibitors at a Python convention running an interactive booth activity:
a **digital art wall** populated by attendees. Attendees write **Python code**
that generates art (static or animated), submit it along with their contact
info, and their piece appears on a big screen at the booth. At the end of the
event we pick the top N pieces and award prizes.

Key principle: this is **code art, not image generation**. Attendees submit
Python source; we render it. Attendees may write code by hand at a booth
laptop running PyCharm, generate it with AI assistance in the IDE, or upload
it via a website from their own devices.

## Architecture (already decided — do not redesign)

Normalize everything to media files; never run attendee code on the display
machine:

1. Attendee submits Python code + name/email/marketing-consent via a web form
   (or from the booth laptop).
2. A **sandboxed render worker** (Docker: `--network none`, memory/CPU/pids
   limits, hard timeout ~60s) executes the code once and produces:
   - a **PNG** for static pieces, or
   - a short **looping MP4/WebM** (~8s @ 30fps, 512×512) for animated pieces.
3. The wall is a **fullscreen web page** on a TV showing a grid of tiles:
   `<img>` for static, muted looping `<video>` for animated. It polls (or
   uses SSE) for new approved pieces and shows a "New piece by <name>!" toast.
4. A small **FastAPI + SQLite** server provides:
   - `POST /submit` — code + contact info → render job queue
   - `GET /wall` — the display grid
   - `GET /piece/{id}` — fullscreen single piece + author (+ optional
     "flip to show source code" view)
   - `GET /admin` — moderation queue (pieces must be approved before display)
     and a winner-picking view.

## Submission contract (already decided)

Attendee code must define exactly one of:

```python
def draw():      # static: returns PIL Image, numpy uint8/float array, or matplotlib Figure
def draw(t):     # animated: t goes 0.0 -> 1.0 over one perfect loop
```



The render harness inspects `draw`'s signature to choose static vs animated,
and a `normalize()` helper converts Figure/PIL/ndarray outputs to uint8 RGB
frames. Matplotlib must use the `Agg` backend in the worker.

A secondary "advanced" format exists for the booth laptop only: live **py5**
sketches, rendered to frames offscreen and encoded to video with the same
pipeline. This is a bonus, not part of the web submission path.

## Current repository state

- Python 3.12, managed with **uv** (use `uv add`, `uv run`; no other package
  managers). Dependencies already include: numpy, matplotlib, pandas, shapely,
  colour, trimesh, svgpathtools, py5, py5jupyter, ipywidgets, jupyterlab.
- `samples/` contains working, contract-compliant example pieces used as demo
  art and as test fixtures for the render pipeline:
  - `plasma_shader.py` — animated `draw(t)`, pure numpy "fragment shader"
  - `flow_field.py` — static `draw()`, numpy + matplotlib
  - `circle_mosaic.py` — static `draw()`, shapely + colour + matplotlib
  - `torus_wireframe.py` — animated `draw(t)`, trimesh + matplotlib
  - `py5_orbits.py` — live py5 sketch (booth-laptop format; does NOT follow
    the contract; do not run it in automated tests — it opens a window)
  - `preview.py` — reference harness: renders a submission file to PNG or
    looping GIF; contains the canonical `normalize()` implementation
- `sample.ipynb`, `data/`, `models/` — scratch/exploration; ignore unless told
  otherwise.

## Constraints and guardrails

- Treat all attendee code as **hostile**. It only ever executes inside the
  sandboxed worker. The web server, wall page, and admin UI never import or
  exec submissions.
- Deterministic re-renders matter: don't inject randomness into the harness.
- Keep the wall page dependency-light (plain HTML/JS or minimal framework);
  it must run smoothly fullscreen on a TV browser with ~50+ video tiles.
- Contact info is collected for marketing: store name, email, consent flag,
  timestamp alongside each submission; make it exportable (CSV) from admin.
- Moderation is mandatory: nothing appears on the wall until approved.
- Follow the existing `draw()` / `draw(t)` contract exactly; `preview.py` is
  the source of truth for output normalization.

## Your task
- Build the FastAPI server, SQLite schema, and job queue described above.
- Build the Docker render worker image and harness (reuse `normalize()` from
  `samples/preview.py`).
- Build the wall page and admin/moderation UI.
- Add tests that render every file in `samples/` (except `py5_orbits.py`)
  through the pipeline and assert output dimensions/format.

Work incrementally, keep modules small, and ask before adding new
dependencies (add them via `uv add`).

