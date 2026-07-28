# PROTOTYPE — Pyodide live canvas (throwaway)

**Question this answers:** can attendees live-edit `draw()` / `draw(t)` Python
(numpy, matplotlib) on the submission website and see it render on a canvas,
fully client-side, via [Pyodide](https://pyodide.org)? Stretch: does
pygame-ce work through Pyodide's experimental SDL support?

This is throwaway code — no error handling beyond what makes it runnable,
no tests, everything in one HTML file. Do not ship it.

## Run

```
uv run python -m http.server 8123 --directory prototypes/pyodide_live_canvas
```

Open http://localhost:8123 (needs internet: Pyodide + wheels come from the
jsDelivr CDN; everything is cached by the browser after the first load).

## What to try

- **starter** / **plasma** — animated `draw(t)`, pure numpy. Watch the
  frame-time/fps readout under the canvas.
- **flow field** — static `draw()`, numpy + matplotlib Figure (copied
  verbatim from `samples/flow_field.py`; normalization is the same
  `normalize()` logic as `samples/preview.py`, ported into the page).
- **pygame-ce (stretch)** — interactive SDL loop drawing straight to the
  canvas; click the canvas to perturb the orbits, Stop ends the loop.
- Edit any code and re-run (Cmd/Ctrl+Enter). Errors and `print()` output land
  in the console pane.

## Measured (Pyodide 314.0.2, wasm runtime, M-series laptop)

Checked headlessly by running the page's exact embedded harness inside the
real Pyodide runtime (Node + CDN wheels) and locally in CPython:

| step | time |
|---|---|
| runtime boot | ~1 s (Node; expect 2–5 s first browser load) |
| numpy + matplotlib + pillow download | ~1.5 s warm CDN, ~15 MB first time |
| plasma `draw(t)` 512×512 frame | ~23 ms → 30 fps easily |
| flow field matplotlib `draw()` | ~300 ms (fine for static) |
| first frame of any submission | +0.5–1 s warmup |

## Verdict

**Feasible.** The core ask — live-edit numpy/matplotlib code following the
existing submission contract and preview it on a canvas — works well, and the
same `normalize()` semantics as the server pipeline apply. pygame-ce also
runs (stretch goal met), but it is explicitly experimental in Pyodide and
outside the `draw()` contract.

## Caveats for the real implementation

- **Preview only, never authoritative.** The sandboxed Docker worker stays
  the source of truth for rendering; the browser preview just reduces
  bad-submission round-trips. Client-side execution is not a sandbox for
  *our* infra (it runs on the attendee's own machine), but do not feed its
  output back to the wall.
- Run Pyodide in a **Web Worker** in production: heavy `draw()` code
  (e.g. the flow field) blocks the main thread/UI in this prototype.
- Package coverage: numpy, matplotlib, pillow, shapely are Pyodide built-ins;
  `colour`/`trimesh`/`svgpathtools` are pure-Python and installable via
  micropip; **py5 will not work** (needs a JVM) — browser preview should
  reject/ignore py5 submissions.
- Matplotlib must be forced to the `Agg` backend in-page (Pyodide's default
  backend renders into the DOM); the harness does this before user code runs.
- Animated matplotlib pieces (like `torus_wireframe`) will preview at only a
  few fps — acceptable for preview, worth a note in the UI.
- pygame path needs `pyodide._api._skip_unwind_fatal_error = true` and a
  canvas with `id="canvas"`; loops must `await asyncio.sleep()` to yield.
  Treat as booth-laptop bonus, not the web path.
