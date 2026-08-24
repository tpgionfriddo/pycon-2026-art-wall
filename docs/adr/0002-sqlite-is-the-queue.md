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
