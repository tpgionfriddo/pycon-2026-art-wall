# Code Art Wall — MVP Plan (confirmed 2026-07-28)

Confirmed in a grilling session; status: **implemented** (`699f5b4`); wall
layout and theme since revised (ADR-0005, ADR-0006).
Vocabulary: see [CONTEXT.md](../CONTEXT.md). Key decisions with rationale:
[docs/adr/](./adr/). Where this plan deviates from `AGENT_BRIEF.md`
(py5 dropped, 5 s loops, no winner-picking view), this plan and the ADRs win.

## 1. Submission page

- CodeMirror 6 (CDN, ESM import) editor + **mandatory Pyodide preview**
  (see ADR-0001). A successful preview render **hard-gates** the submit
  button; there is no escape hatch.
- Supported Packages (identical in preview and worker):
  `numpy, matplotlib, Pillow, pandas, shapely, scipy` (Pyodide built-ins) +
  `colour, trimesh, svgpathtools` (micropip / pure-python wheels).
  py5 is not supported anywhere.
- Draw Contract enforced client-side before submit: exactly one of
  `draw()` (static) or `draw(t)` (animated, t: 0→1 over one loop).
- Form fields: code, name, email, marketing-consent checkbox (all required).

## 2. Server (FastAPI + SQLite)

- `POST /submit` — guards: 32 KB code cap; name/email/consent required;
  per-IP rate limit ~5 submissions / 10 min (in-process counter);
  queue-depth cap (~100 queued → HTTP 429 "try again later").
  On success: insert row (status `queued`), redirect to status page.
- `GET /submission/{id}` — status page polling a JSON endpoint through
  `queued → rendering → rendered → approved | rejected | failed`;
  render errors are shown here.
- `GET /wall` — the wall page (below).
- `GET /piece/{id}` — fullscreen single piece + author, with
  "flip to show source" view.
- `GET /admin` — HTTP Basic auth (single shared password from env var)
  covering the page, its API routes, and CSV export. Moderation queue with
  approve/reject on rendered pieces. CSV export of **all** submissions
  (name, email, consent, timestamp, status). No winner-picking tooling —
  deliberately cut.
- SQLite schema: single `submissions` table (id, code, name, email, consent,
  created_at, status, kind static/animated, media path, error, timestamps).
  Rejected submissions are kept, never displayed.

## 3. Render worker (see ADR-0002)

- Separate host-side process (`uv run python -m artwall.worker`) polls
  SQLite, claims one `queued` job at a time.
- Per job: `docker run --rm --network none --memory 1g --cpus 1
  --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges`, code
  mounted read-only, **60 s kill enforced from the host side**; writes media
  to a shared directory, updates the row. The root filesystem stays writable
  on purpose — charting writes to a temporary directory.
- The sandbox result is untrusted: the submission shares the output directory
  with the harness, so only the media filenames the harness may produce are
  accepted, and any unexpected failure fails that submission alone rather
  than the worker loop.
- Harness inside the container reuses `normalize()` from
  `samples/preview.py`; matplotlib forced to Agg.
- Output spec:
  - static → PNG, native size downscaled to fit 1024×1024;
  - animated → 150 frames @ 30 fps (5 s perfect loop), scaled to fit
    512×512, encoded in-container by ffmpeg to **WebM/VP9** (ADR-0003);
  - aspect ratio always preserved, fit-in-box, no crop/stretch.
- Worker image ships exactly the Supported Packages + ffmpeg.

## 4. Wall

- Plain HTML/JS (no framework). Polls a JSON list of approved pieces every
  ~5 s, diffs client-side; new piece → tile added + "New piece by <name>!"
  toast.
- Grid shows **all** approved pieces as uniform square tiles that always
  fill the screen: tile size is computed from piece count + viewport, so
  few pieces render large and tiles shrink without limit as the wall grows;
  the page never scrolls, nothing is ever hidden or rotated out (ADR-0005).
  Size changes animate (~0.5 s).
- `<img>` for static, muted autoplaying looping `<video>` for animated.
- All six pages share the JetBrains branding: JetBrains Mono for
  headings/code and `#6B57FF` as the single interactive colour. Headings are
  near-black; the logo gradient is not used as an accent anywhere. The five
  light pages are submit, status, piece, terms and admin; the wall alone uses
  a dark ground and carries the PyCharm logo (ADR-0006 as amended).

## 5. Hosting (see ADR-0004)

- Cloud VPS + public domain runs server, worker, and Docker; booth QR code
  and wall TV both point at the public URL.
- Fallback: identical stack on the booth laptop (Docker + two `uv run`
  processes); nothing in the code may assume VPS specifics.

## 6. Tests

- Every contract-compliant file in `samples/` (all except `py5_orbits.py`,
  which stays in the repo documented as unsupported) rendered through the
  real pipeline, asserting output dimensions and format.
- Guard tests: submit validation (size cap, missing fields), rate limit,
  moderation gating (unapproved pieces never in the wall JSON), admin auth.

## Layout defaults

- Code in an `artwall/` package: `server`, `worker`, `db` modules; templates
  and static files alongside; worker harness + Dockerfile under the package
  or a sibling `worker/` dir — implementer's choice, keep modules small.
- Dependencies via `uv add` only; FastAPI etc. must be added on
  implementation start.

## Blocking acceptance items (before the event)

1. **50-tile playback smoke test on the actual booth wall hardware**
   (VP9 decode risk, ADR-0003); documented fallback: re-encode to H.264.
2. End-to-end dry run: submit from a phone on mobile data → preview →
   moderate → piece appears on the wall.
