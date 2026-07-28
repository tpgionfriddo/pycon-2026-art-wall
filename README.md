# Code Art Wall

A conference-booth activity: attendees write Python that generates art in a
browser editor with a **mandatory live preview** (Pyodide), submit it, a
sandboxed Docker worker renders it server-side, a human moderator approves
it, and the piece appears on the big-screen **wall**.

Docs: [MVP plan](docs/MVP-PLAN.md) · [decision records](docs/adr/) ·
[vocabulary](CONTEXT.md). Spec background: `AGENT_BRIEF.md` (the plan and
ADRs win where they differ).

## Running the stack

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker.

```bash
# 1. install dependencies
uv sync

# 2. build the sandbox image (Supported Packages + ffmpeg)
docker build -t artwall-worker -f worker/Dockerfile .

# 3. the web server (submission page, wall, admin)
ARTWALL_ADMIN_PASSWORD=change-me uv run uvicorn artwall.server:create_app --factory --host 0.0.0.0 --port 8000

# 4. the render worker, in a second terminal (ADR-0002)
uv run python -m artwall.worker
```

Pages: `/` submit (editor + preview) · `/wall` booth TV · `/piece/{id}`
single piece · `/submission/{id}` attendee status · `/admin` moderation
(HTTP Basic, password = `ARTWALL_ADMIN_PASSWORD`).

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ARTWALL_ADMIN_PASSWORD` | *(unset — admin locked)* | shared moderator password |
| `ARTWALL_DATA_DIR` | `data` | SQLite DB + rendered media |
| `ARTWALL_WORKER_IMAGE` | `artwall-worker` | sandbox image tag |

The submission page needs internet (Pyodide + CodeMirror come from CDNs) —
see ADR-0001/ADR-0004.

## Tests

```bash
uv run pytest            # server/db guards run everywhere;
                         # pipeline tests need Docker + the artwall-worker image
```

## Samples

`samples/` holds contract examples (`draw()` static, `draw(t)` animated) and
the local preview harness `samples/preview.py`. **`samples/py5_orbits.py` is
unsupported** — py5 is JVM-based and cannot run in the browser preview, so
it was dropped from the contest entirely (ADR-0001).

## Layout

- `artwall/` — `server` (FastAPI), `worker` (host-side job runner),
  `db` (SQLite = the job queue), `config`, `templates/`
- `worker/` — sandbox `Dockerfile` + `render_job.py` (in-container harness)
- `prototypes/` — throwaway Pyodide feasibility spike (superseded by `/`)

## Before the event (blocking, MVP plan)

1. 50-tile VP9 playback smoke test on the real booth hardware (ADR-0003).
2. End-to-end dry run: phone on mobile data → preview → moderate → wall.
