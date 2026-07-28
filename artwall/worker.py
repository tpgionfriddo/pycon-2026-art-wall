"""Render worker (ADR-0002): a host-side process that polls SQLite, claims
one queued job at a time and runs it in a short-lived hardened container.

Run: uv run python -m artwall.worker
Requires the sandbox image: docker build -t artwall-worker -f worker/Dockerfile .
"""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import db
from .config import Settings

DOCKER_FLAGS = ["--network", "none", "--memory", "1g", "--cpus", "1",
                "--pids-limit", "128"]


class RenderError(Exception):
    """A job failed inside (or around) the sandbox; message goes to the row."""


def run_container(code: str, out_dir: Path, settings: Settings,
                  job_id: int) -> dict:
    """One hardened `docker run` per job; the 60 s kill is enforced host-side."""
    container = f"artwall-job-{job_id}"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "submission.py"
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

    result_file = out_dir / "result.json"
    if not result_file.exists():
        detail = (proc.stderr or "").strip()[-2000:]
        raise RenderError("sandbox produced no result"
                          + (f":\n{detail}" if detail else ""))
    result = json.loads(result_file.read_text())
    if result.get("error"):
        raise RenderError(result["error"])
    return result


def process_one(conn, settings: Settings) -> bool:
    """Claim and render a single job. Returns False when the queue is empty."""
    row = db.claim_next_queued(conn)
    if row is None:
        return False
    job_id = row["id"]
    print(f"[worker] rendering #{job_id} by {row['name']}", flush=True)
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        try:
            result = run_container(row["code"], out_dir, settings, job_id)
            suffix = "png" if result["kind"] == "static" else "webm"
            media_name = f"{job_id}.{suffix}"
            settings.media_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(out_dir / result["media"], settings.media_dir / media_name)
            db.mark_rendered(conn, job_id, result["kind"], media_name)
            print(f"[worker] #{job_id} rendered -> {media_name}", flush=True)
        except RenderError as exc:
            db.mark_failed(conn, job_id, str(exc))
            print(f"[worker] #{job_id} failed: {exc}", flush=True)
    return True


def main() -> None:
    settings = Settings.from_env()
    conn = db.connect(settings.db_path)
    requeued = db.requeue_stale_rendering(conn)
    if requeued:
        print(f"[worker] requeued {requeued} job(s) left over from a crash",
              flush=True)
    print(f"[worker] polling {settings.db_path} "
          f"(image: {settings.worker_image})", flush=True)
    while True:
        if not process_one(conn, settings):
            time.sleep(settings.poll_interval_s)


if __name__ == "__main__":
    main()
