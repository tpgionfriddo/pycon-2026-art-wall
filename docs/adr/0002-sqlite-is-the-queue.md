# SQLite is the job queue; a host-side worker spawns one container per job

There is no message broker or task-queue library. `POST /submit` inserts a
submission row with status `queued`; a separate host-side worker process
(`uv run`, long-lived) polls SQLite, claims one job at a time, and runs a
short-lived hardened container per job (`docker run --rm --network none`,
memory/CPU/pids limits, all capabilities dropped, no privilege escalation,
~60 s host-side kill). The worker writes the rendered
media to a shared directory and updates the row.

Chosen over Celery/Redis (needless infrastructure for a single-booth,
single-worker event) and over an in-process FastAPI background task (couples
the web server to Docker and loses queued work on crash — with SQLite as the
queue, jobs survive any restart). The web server never touches Docker.

## Amendment (2026-08-24): the worker is containerised (ADR-0007)

The worker is no longer a host-side process. It runs as a container of the
Compose stack and drives the **host's** Docker daemon through a mounted
socket, which is why its scratch area has to be bind-mounted at one identical
absolute path on both sides. Everything else above stands: SQLite is still the
queue, still one hardened short-lived container per job, and the web server
still never touches Docker.
