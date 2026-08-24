"""FastAPI server: submission intake, status, wall, piece, admin.

The server never touches Docker (ADR-0002) — it only inserts queued rows
that the worker process picks up.

Run: uv run uvicorn artwall.server:create_app --factory
"""
import csv
import io
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .config import FPS, FRAMES, SUPPORTED_PACKAGES, Settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
# Committed page assets (the wall logo). Kept apart from the rendered-media
# mount, which serves untracked runtime state (ADR-0006).
STATIC_DIR = Path(__file__).parent / "static"


class RateLimiter:
    """In-process sliding-window counter, keyed by client IP."""

    def __init__(self, max_events: int, window_s: float):
        self.max_events = max_events
        self.window_s = window_s
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self.window_s:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True


def _media_url(row) -> str | None:
    return f"/media/{row['media_path']}" if row["media_path"] else None


def _submission_json(row) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "kind": row["kind"],
        "error": row["error"],
        "media_url": _media_url(row),
        "name": row["name"],
    }


def _piece_json(row) -> dict:
    """Wall payload: no contact data, no code."""
    return {
        "id": row["id"],
        "kind": row["kind"],
        "media_url": _media_url(row),
        "name": row["name"],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    db.connect(settings.db_path).close()  # create schema up front

    app = FastAPI(title="Code Art Wall")
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    limiter = RateLimiter(settings.rate_limit_max, settings.rate_limit_window_s)
    security = HTTPBasic()

    def get_conn():
        conn = db.connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
        ok = bool(settings.admin_password) and secrets.compare_digest(
            credentials.password.encode(), settings.admin_password.encode()
        )
        if not ok:
            raise HTTPException(status_code=401, detail="Bad credentials",
                                headers={"WWW-Authenticate": "Basic"})

    # ---- attendee-facing pages ---------------------------------------------

    @app.get("/")
    def submission_page(request: Request):
        return templates.TemplateResponse(request, "submit.html", {
            "packages": SUPPORTED_PACKAGES,
            "frames": FRAMES,
            "fps": FPS,
        })

    @app.post("/submit")
    def submit(request: Request,
               code: str = Form(...),
               name: str = Form(...),
               email: str = Form(...),
               consent: bool = Form(False),
               conn=Depends(get_conn)):
        if len(code.encode("utf-8")) > settings.max_code_bytes:
            raise HTTPException(413, "Code exceeds the 32 KB limit")
        if not code.strip() or not name.strip() or not email.strip():
            raise HTTPException(400, "Code, name and email are required")
        if not consent:
            raise HTTPException(400, "Consent is required")
        if db.count_queued(conn) >= settings.max_queue_depth:
            raise HTTPException(429, "Render queue is full — try again later")
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(ip):
            raise HTTPException(429, "Too many submissions — try again later")
        submission_id = db.create_submission(
            conn, code, name.strip(), email.strip(), consent)
        return RedirectResponse(f"/submission/{submission_id}", status_code=303)

    @app.get("/submission/{submission_id}")
    def status_page(request: Request, submission_id: int,
                    conn=Depends(get_conn)):
        row = db.get_submission(conn, submission_id)
        if row is None:
            raise HTTPException(404)
        return templates.TemplateResponse(request, "status.html",
                                          {"submission": _submission_json(row)})

    @app.get("/api/submission/{submission_id}")
    def submission_status(submission_id: int, conn=Depends(get_conn)):
        row = db.get_submission(conn, submission_id)
        if row is None:
            raise HTTPException(404)
        return _submission_json(row)

    # ---- wall ---------------------------------------------------------------

    @app.get("/wall")
    def wall_page(request: Request):
        return templates.TemplateResponse(request, "wall.html", {})

    @app.get("/api/wall")
    def wall_json(conn=Depends(get_conn)):
        rows = db.list_by_status(conn, "approved")
        return {"pieces": [_piece_json(r) for r in rows]}

    @app.get("/piece/{submission_id}")
    def piece_page(request: Request, submission_id: int,
                   conn=Depends(get_conn)):
        row = db.get_submission(conn, submission_id)
        if row is None or row["status"] != "approved":
            raise HTTPException(404)
        return templates.TemplateResponse(request, "piece.html", {
            "piece": _piece_json(row),
            "code": row["code"],
        })

    # ---- admin (HTTP Basic on the page, its API routes, and the export) ----

    @app.get("/admin", dependencies=[Depends(require_admin)])
    def admin_page(request: Request, conn=Depends(get_conn)):
        pending = db.list_by_status(conn, "rendered")
        counts = {status: 0 for status in db.STATUSES}
        for row in db.list_all(conn):
            counts[row["status"]] += 1
        return templates.TemplateResponse(request, "admin.html", {
            "pending": [dict(r) | {"media_url": _media_url(r)} for r in pending],
            "counts": counts,
        })

    @app.post("/admin/submissions/{submission_id}/approve",
              dependencies=[Depends(require_admin)])
    def approve(submission_id: int, conn=Depends(get_conn)):
        db.moderate(conn, submission_id, approved=True)
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/submissions/{submission_id}/reject",
              dependencies=[Depends(require_admin)])
    def reject(submission_id: int, conn=Depends(get_conn)):
        db.moderate(conn, submission_id, approved=False)
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin/export.csv", dependencies=[Depends(require_admin)])
    def export_csv(conn=Depends(get_conn)):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "name", "email", "consent", "created_at", "status"])
        for row in db.list_all(conn):
            writer.writerow([row["id"], row["name"], row["email"],
                             row["consent"], row["created_at"], row["status"]])
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=submissions.csv"})

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
