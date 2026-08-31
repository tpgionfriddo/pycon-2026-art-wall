# Code Art Wall

A conference-booth activity: attendees write Python that generates art in a
browser editor with a **mandatory live preview** (Pyodide), submit it, a
sandboxed Docker worker renders it server-side, a human moderator approves
it, and the piece appears on the big-screen **wall**.

Docs: **[runbook](docs/RUNBOOK.md)** (symptom → action, for the booth) ·
[MVP plan](docs/MVP-PLAN.md) · [decision records](docs/adr/) ·
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

# 3. the reverse proxy, the server, and one render worker
docker compose up -d --build
```

Everything is served through the proxy, on the ports it publishes —
`http://localhost:8000` with the values `.env.example` ships, or the same port
on the machine's address from another device. The server publishes no port of
its own, so the proxy is the only way in.

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

Pages: `/` submit (editor + preview) · `/terms` terms and conditions ·
`/wall` booth TV · `/piece/{id}` single piece · `/submission/{id}` attendee
status · `/admin` moderation (HTTP Basic, password =
`ARTWALL_ADMIN_PASSWORD`).

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ARTWALL_ADMIN_PASSWORD` | *(unset — admin locked)* | shared moderator password |
| `ARTWALL_DATA_DIR` | `data` | SQLite DB + rendered media |
| `ARTWALL_WORKER_IMAGE` | `artwall-worker` | sandbox image tag |
| `ARTWALL_SCRATCH_DIR` | *(unset — system temp)* | base for the worker's per-job scratch |
| `ARTWALL_RATE_LIMIT_MAX` | `60` | submissions one client address may make per window |
| `ARTWALL_RATE_LIMIT_WINDOW_S` | `600` | the window, in seconds |
| `ARTWALL_MAX_QUEUE_DEPTH` | `100` | queued submissions before `/submit` refuses |
| `ARTWALL_MAX_CODE_BYTES` | `32768` | largest submission the server accepts |
| `ARTWALL_RENDER_TIMEOUT_S` | `180` | seconds one render may take before it is killed |
| `ARTWALL_RENDER_CPUS` | `2.0` | CPUs one render may use; only one render runs at a time |
| `ARTWALL_POLL_INTERVAL_S` | `2.0` | how often the worker checks an empty queue |
| `ARTWALL_SITE_ADDRESS` | `:80` | what the proxy answers to; a bare domain turns TLS on |
| `ARTWALL_HTTP_PORT` | `80` | host port for the proxy's HTTP listener |
| `ARTWALL_HTTPS_PORT` | `443` | host port for the proxy's HTTPS listener |
| `ARTWALL_DOCKER_SOCK` | `/var/run/docker.sock` | host daemon socket given to the worker |

`.env.example` overrides the two ports to 8000 and 8443, because a laptop
usually has something on 80 already. The VPS wants the defaults.

Under Compose these come from `.env` (see `.env.example`), with two caveats.
The last four are Compose's and the proxy's alone and mean nothing to the
code. And `ARTWALL_DATA_DIR` there names the *host* directory to bind-mount;
inside both containers the path is always `/data`, which is what the
application reads.

`ARTWALL_SCRATCH_DIR` only matters once the worker itself runs in a
container, where it must be an absolute path bind-mounted identically inside
and outside — see `check_scratch_base` in `artwall/worker.py`. The worker
refuses to start on a base that cannot hold. `compose.yaml` bind-mounts that
one variable onto itself for exactly this reason. Docker creates the directory
on first `up` if it is missing, owned by root on Linux; nothing but the worker
writes there, so that is left alone.

The submission page needs internet (Pyodide + CodeMirror come from CDNs) —
see ADR-0001/ADR-0004.

## Deploying to the VPS

Production is a cloud VPS behind a public domain (ADR-0004). The stack is
deployed there as a
[Portainer git stack](https://docs.portainer.io/user/docker/stacks/add) from
this public repository, so that a fix can be shipped from a phone tether at
the booth. Nothing about the stack differs from the laptop one except the
values it is given.

ADR-0007 records why the deployment looks the way it does — the containerised
worker driving the *host* Docker daemon, the same-path scratch mount, the
proxy's baked-in configuration — and is worth reading before changing any of
it, because each of those fails silently when "fixed".

**Before the stack exists.** Lower the TTL on the DNS record a good while
before pointing it at the VPS — a mistake then costs minutes rather than
hours. Certificate issuance needs the name to resolve to the box and ports
80 and 443 to be reachable from the internet.

**The stack.** *Stacks → Add stack → Git Repository*, compose path
`compose.yaml`, and these environment variables:

| Variable | Value |
| --- | --- |
| `ARTWALL_ADMIN_PASSWORD` | the moderator password — this is the only place it exists |
| `ARTWALL_SITE_ADDRESS` | the bare domain, e.g. `artwall.example.com`; this is the switch that turns TLS on |
| `ARTWALL_DATA_DIR` | an absolute path outside the stack's own directory, e.g. `/srv/artwall/data` |

Leave the two port variables unset. They default to 80 and 443, which is what
the certificate challenge needs and what a browser will try.

`ARTWALL_DATA_DIR` has to be absolute, and the failure if it is not is silent:
the daemon resolves bind-mount sources on the host, where the stack's own
directory does not exist, so a relative path lands somewhere nobody will think
to look and the database goes with it. The stack bind-mounts nothing else from
the repository for the same reason — the proxy's configuration is built into
its image rather than mounted.

**The sandbox image.** The stack cannot build it: `sandbox-image` is a
build-only service behind a profile nothing enables, so `up` skips it (this is
deliberate — see the comment in `compose.yaml`). It has to be built once on
the box, and again whenever `worker/Dockerfile` or the Supported Packages
change. Either through Portainer, *Images → Build a new image*, naming the
image `artwall-worker` and building from the repository URL with Dockerfile
path `worker/Dockerfile` — or over SSH from a clone:

```bash
git clone https://github.com/tpgionfriddo/pycon-2026-art-wall /srv/artwall/src
cd /srv/artwall/src
# the password is irrelevant to a build; Compose only insists on a value
ARTWALL_ADMIN_PASSWORD=unused docker compose build sandbox-image
```

**Shipping a change.** Push to `main`, then *Pull and redeploy* on the stack.
Leave *Re-pull image* off: these images are built on the box, not pulled from
a registry, and asking for the newest copy of one that exists nowhere fails
the deployment.

Check that the change actually landed. Portainer does build images from a git
stack, but it is not an officially supported feature and older versions did
not rebuild on update. If a redeploy serves the old code, rebuild from the
clone above and redeploy again — Compose recreates a container whose image
has changed:

```bash
cd /srv/artwall/src && git pull
ARTWALL_ADMIN_PASSWORD=unused docker compose build
```

That builds the application and proxy images. It does not touch the sandbox
image, which is behind the profile and named explicitly, as above.

**What survives a redeploy.** The database and the rendered media, because
`ARTWALL_DATA_DIR` is a host path outside the stack directory. The
certificates, because they live in a named volume. Neither is removed by a
stack update; only deleting the stack *and* its volumes would take the
certificates, and nothing but `rm` would take the database.

## After the event: the static gallery

`python -m artwall.gallery` turns a deployed wall into a directory of plain
files — one `index.html` and one media file per piece — for GitHub Pages to
serve. Every piece a moderator approved, including the ones archived when the
event moved on to a new day, each with the Python that drew it. See
ADR-0009.

```bash
uv sync --group gallery      # the generator needs Pygments; the server does not

# ARTWALL_ADMIN_PASSWORD is read from the environment, or prompted for
python -m artwall.gallery --base-url https://artwall.example.com \
    --winners 12,45,88 --out ../artwall-gallery
```

`--first 34,1,2` pins pieces to the front of the grid in the order given, for
the ones that introduce the gallery rather than compete in it. The winners
follow them, then everything else in id order, which is the order the event
happened in. An id named in both is placed once.

`--winners` takes the daily winners in day order: the first id is day one.
Nothing in the database records the judges' decision, so this flag is the
only place it exists. A winner keeps its place in the grid and wears a small
pixel trophy carrying its day number.

**Publish it from its own repository**, not this one. The media runs to
hundreds of megabytes, Portainer clones this repository on every redeploy,
and the point of that (ADR-0007) is shipping a fix from a phone tether at the
booth. Git objects are permanent and a branch does not help — a clone fetches
them all.

```bash
gh repo create <event>-art-gallery --public
cd ../artwall-gallery && git init && git add -A
git commit -m "The art wall, <event>"
git push --set-upstream <url> main
# then: Settings -> Pages -> Deploy from a branch -> main / (root)
```

**Taking a piece out of the published gallery** is `rm media/14.*` in that
repository and nothing else — the tile hides itself when its image does not
load, and the grid closes up. The glob matters: an animated piece is two
files, the loop and the still extracted from it, and they share a stem for
exactly this reason. A later rebuild fetches it again, so a removal that has
to survive one goes in `--exclude 14,22`.

Animated pieces get that still from **ffmpeg**, at build time. Without it the
build still works and says so, but the grid opens as a page of empty boxes:
a `<video>` paints nothing until it has decoded a frame, and a phone will not
decode seventy of them. With the stills, the grid is images and a video is
attached to a tile only while it is on screen. What is on screen is the
bound: about ten pieces on a phone, fifty on a desktop, all of them moving.
The ceiling is the browser's own limit on media
players, seventy five, so a gallery smaller than that plays every piece on
screen however large the screen. A larger event reaches it, and then the
tiles nearest the middle of the screen are the ones that play.

Everything published is byline-only: no contact name, no email, no phone, no
company. The export endpoint the generator reads leaves those out entirely,
rather than leaving it to the generator to drop them. Clause 11 of the
supplied terms is what permits the publication, and clause 12 the credit.

## Operating it

[`docs/RUNBOOK.md`](docs/RUNBOOK.md) is one page of symptom → action for
booth staff: a queue that stopped moving, every submission failing, a blank
or stuttering wall, taking a piece off the wall, restarting a container,
restoring the database, and exporting the contact list — plus which failures
are safe to ignore until after the event.

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
  `db` (SQLite = the job queue), `config`, `gallery` (the post-event static
  site generator), `templates/`,
  `static/` (committed page assets — the wall logo)
- `worker/` — sandbox `Dockerfile` + `render_job.py` (in-container harness)
- `proxy/` — the reverse proxy image: `Dockerfile` + the `Caddyfile` that
  terminates TLS in front of the server
- `Dockerfile`, `compose.yaml`, `.env.example` — the application image and
  the stack that runs it
- `prototypes/` — throwaway Pyodide feasibility spike (superseded by `/`)

## Before the event (blocking, MVP plan)

1. 50-tile VP9 playback smoke test on the real booth hardware (ADR-0003).
2. End-to-end dry run: phone on mobile data → preview → moderate → wall.
