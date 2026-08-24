# Code Art Wall

A conference-booth activity: attendees write Python that generates art in a
browser editor with a **mandatory live preview** (Pyodide), submit it, a
sandboxed Docker worker renders it server-side, a human moderator approves
it, and the piece appears on the big-screen **wall**.

Docs: [MVP plan](docs/MVP-PLAN.md) · [decision records](docs/adr/) ·
[vocabulary](CONTEXT.md). Spec background: `AGENT_BRIEF.md` (the plan and
ADRs win where they differ).

## Running the stack

Prerequisites: Docker. (For the development loop below, also
[uv](https://docs.astral.sh/uv/).)

```bash
# 1. configure — at minimum set ARTWALL_ADMIN_PASSWORD; the stack refuses
#    to start without it
cp .env.example .env

# 2. build the sandbox image (Supported Packages + ffmpeg) in the host
#    daemon, under the tag the worker starts each job in. This is a
#    build-only service and never runs.
docker compose build sandbox-image

# 3. the server and one render worker
docker compose up -d --build
```

The database and the rendered media live in `ARTWALL_DATA_DIR` (`./data`),
bind-mounted into both containers, so they survive `docker compose down`.

### Development loop

The same two processes on the host, without containers:

```bash
uv sync
docker build -t artwall-worker -f worker/Dockerfile .
ARTWALL_ADMIN_PASSWORD=change-me uv run uvicorn artwall.server:create_app --factory --host 0.0.0.0 --port 8000
uv run python -m artwall.worker   # second terminal (ADR-0002)
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
| `ARTWALL_SCRATCH_DIR` | *(unset — system temp)* | base for the worker's per-job scratch |
| `ARTWALL_PORT` | `8000` | host port the stack publishes |
| `ARTWALL_DOCKER_SOCK` | `/var/run/docker.sock` | host daemon socket given to the worker |

Under Compose these come from `.env` (see `.env.example`), with two caveats.
`ARTWALL_PORT` and `ARTWALL_DOCKER_SOCK` are Compose's alone and mean nothing
to the code. And `ARTWALL_DATA_DIR` there names the *host* directory to
bind-mount; inside both containers the path is always `/data`, which is what
the application reads.

`ARTWALL_SCRATCH_DIR` only matters once the worker itself runs in a
container, where it must be an absolute path bind-mounted identically inside
and outside — see `check_scratch_base` in `artwall/worker.py`. The worker
refuses to start on a base that cannot hold. `compose.yaml` bind-mounts that
one variable onto itself for exactly this reason. Docker creates the directory
on first `up` if it is missing, owned by root on Linux; nothing but the worker
writes there, so that is left alone.

The submission page needs internet (Pyodide + CodeMirror come from CDNs) —
see ADR-0001/ADR-0004.

## Tests

```bash
uv run pytest            # server/db guards run everywhere;
                         # pipeline tests need Docker + the artwall-worker image
```

The stack itself is deliberately not covered here — it is verified by the
pre-flight checklist instead.

## Samples

`samples/` holds contract examples (`draw()` static, `draw(t)` animated) and
the local preview harness `samples/preview.py`. **`samples/py5_orbits.py` is
unsupported** — py5 is JVM-based and cannot run in the browser preview, so
it was dropped from the contest entirely (ADR-0001).

## Layout

- `artwall/` — `server` (FastAPI), `worker` (claims jobs and drives the host
  Docker daemon),
  `db` (SQLite = the job queue), `config`, `templates/`,
  `static/` (committed page assets — the wall logo)
- `worker/` — sandbox `Dockerfile` + `render_job.py` (in-container harness)
- `Dockerfile`, `compose.yaml`, `.env.example` — the application image and
  the stack that runs it
- `prototypes/` — throwaway Pyodide feasibility spike (superseded by `/`)

## Before the event (blocking, MVP plan)

1. 50-tile VP9 playback smoke test on the real booth hardware (ADR-0003).
2. End-to-end dry run: phone on mobile data → preview → moderate → wall.
