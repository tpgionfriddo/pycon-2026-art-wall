"""Render worker (ADR-0002): polls SQLite, claims one queued job at a time and
runs it in a short-lived hardened container.

The daemon it drives is always the host's, whether this process runs on the
host or in a container of its own — hence `check_scratch_base`, which keeps
the two views of a path in step. ADR-0002 describes only the host-side shape;
ADR-0007 records the containerised one.

Run: uv run python -m artwall.worker  (or `docker compose up worker`)
Requires the sandbox image: docker compose build sandbox-image
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import db
from .config import MEDIA_NAMES, Settings

# A read-only root filesystem is deliberately absent: charting writes to a
# temporary directory, and there is no time before the event to verify that
# against every Supported Package (ADR-0001).
DOCKER_FLAGS = ["--network", "none", "--memory", "1g", "--cpus", "1",
                "--pids-limit", "128", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges"]


class RenderError(Exception):
    """A job failed inside (or around) the sandbox; message goes to the row."""


class ScratchBaseError(Exception):
    """The configured scratch base cannot mean to the daemon what it means
    here, so the worker must not start."""


def check_scratch_base(settings: Settings) -> None:
    """Refuse a scratch base the Docker daemon would read as something else.

    Per-job scratch is handed to the daemon as a bind-mount source, and the
    daemon resolves those on the host — not in whatever filesystem this
    process sees. A relative source is read as a named volume, and an
    absolute one absent from the host is created there empty and mounted over
    the submission. Both fail every render in a way that reads like broken
    attendee code, so a base that is not an existing absolute directory has
    to stop the worker instead of being created here.
    """
    base = settings.scratch_dir
    if base is None:
        return
    if not base.is_absolute():
        raise ScratchBaseError(
            f"the scratch base {base} is relative; the Docker daemon would "
            f"read it as a named volume. Set ARTWALL_SCRATCH_DIR to an "
            f"absolute path.")
    if not base.is_dir():
        raise ScratchBaseError(
            f"the scratch base {base} is not a directory. It must exist at "
            f"this exact path on the Docker host too, so a containerised "
            f"worker has to bind-mount it at the same absolute path.")


@contextmanager
def job_scratch(settings: Settings) -> Iterator[Path]:
    """A scratch directory for one job, removed when the job finishes.

    Built under the configured scratch base (`check_scratch_base`), or in the
    system temporary directory when there is none, as for a host-side worker.
    """
    with tempfile.TemporaryDirectory(dir=settings.scratch_dir) as td:
        yield Path(td)


def run_container(code: str, out_dir: Path, settings: Settings,
                  job_id: int) -> tuple[str, str]:
    """One hardened `docker run` per job; the 60 s kill is enforced host-side.

    Returns the validated (kind, media filename) the sandbox produced.
    """
    container = f"artwall-job-{job_id}"
    with job_scratch(settings) as td:
        src = td / "submission.py"
        src.write_text(code)
        cmd = ["docker", "run", "--rm", "--name", container, *DOCKER_FLAGS,
               "-v", f"{src}:/job/submission.py:ro",
               "-v", f"{out_dir}:/out",
               settings.worker_image,
               "python", "/app/render_job.py", "/job/submission.py", "/out"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=settings.render_timeout_s)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", container], capture_output=True)
            raise RenderError(
                f"render exceeded {settings.render_timeout_s} s and was killed")

    return read_result(out_dir, proc.stderr or "")


def read_result(out_dir: Path, stderr: str) -> tuple[str, str]:
    """Read the sandbox's result.json into a validated (kind, media filename).

    Submission code shares the output directory with the harness and can
    rewrite result.json, so nothing found here is believed on sight.
    """
    result_file = out_dir / "result.json"
    if not result_file.exists():
        detail = stderr.strip()[-2000:]
        raise RenderError("sandbox produced no result"
                          + (f":\n{detail}" if detail else ""))
    try:
        result = json.loads(result_file.read_text())
    except (OSError, ValueError) as exc:
        raise RenderError(f"sandbox result was unreadable: {exc}")
    if not isinstance(result, dict):
        raise RenderError("sandbox result was not an object")
    if result.get("error"):
        raise RenderError(str(result["error"])[-2000:])
    return validate_media(result)


def validate_media(result: dict) -> tuple[str, str]:
    """Reduce a sandbox result to the (kind, media filename) it may name."""
    kind = result.get("kind")
    if not isinstance(kind, str) or kind not in MEDIA_NAMES:
        raise RenderError(f"sandbox reported an unknown kind: {kind!r}")
    expected = MEDIA_NAMES[kind]
    if result.get("media") != expected:
        raise RenderError(f"sandbox named media {result.get('media')!r}, "
                          f"expected {expected!r}")
    return kind, expected


def render_submission(conn, settings: Settings, row) -> None:
    """Render one claimed job and publish its media."""
    job_id = row["id"]
    with job_scratch(settings) as out_dir:
        kind, media = run_container(row["code"], out_dir, settings, job_id)
        source = out_dir / media
        # The name is the harness's, but the file behind it is the
        # submission's: a symlink here would move a host file onto the wall.
        if source.is_symlink() or not source.is_file():
            raise RenderError(f"sandbox media {media} is not a regular file")
        media_name = f"{job_id}{Path(media).suffix}"
        settings.media_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(source, settings.media_dir / media_name)
        db.mark_rendered(conn, job_id, kind, media_name)
        print(f"[worker] #{job_id} rendered -> {media_name}", flush=True)


def process_one(conn, settings: Settings) -> bool:
    """Claim and render a single job. Returns False when the queue is empty."""
    row = db.claim_next_queued(conn)
    if row is None:
        return False
    job_id = row["id"]
    print(f"[worker] rendering #{job_id} by {row['name']}", flush=True)
    try:
        render_submission(conn, settings, row)
    except RenderError as exc:
        db.mark_failed(conn, job_id, str(exc))
        print(f"[worker] #{job_id} failed: {exc}", flush=True)
    except Exception:
        # A hostile submission must fail alone. Letting anything else out of
        # here kills the loop, and the stale-job requeue hands the same job
        # straight back on restart — a crash-loop that stops the wall.
        db.mark_failed(conn, job_id, "the render worker hit an internal "
                                     "error and skipped this piece")
        print(f"[worker] #{job_id} failed unexpectedly:\n"
              f"{traceback.format_exc(limit=8)}", flush=True)
    return True


def poll_once(conn, settings: Settings) -> bool:
    """`process_one` behind a last-resort guard.

    Even failing to record a failure must not stop the loop: the job is left
    `rendering`, so it is skipped rather than requeued, and the next queued
    submission still renders.
    """
    try:
        return process_one(conn, settings)
    except Exception:
        print(f"[worker] recovered from a fatal error in the loop:\n"
              f"{traceback.format_exc(limit=8)}", flush=True)
        return False


def main() -> None:
    # Submission names and tracebacks are echoed here; a console that cannot
    # encode them must not take the worker down with it.
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    settings = Settings.from_env()
    try:
        check_scratch_base(settings)
    except ScratchBaseError as exc:
        sys.exit(f"[worker] {exc}")
    conn = db.connect(settings.db_path)
    requeued = db.requeue_stale_rendering(conn)
    if requeued:
        print(f"[worker] requeued {requeued} job(s) left over from a crash",
              flush=True)
    print(f"[worker] polling {settings.db_path} "
          f"(image: {settings.worker_image})", flush=True)
    while True:
        if not poll_once(conn, settings):
            time.sleep(settings.poll_interval_s)


if __name__ == "__main__":
    main()
