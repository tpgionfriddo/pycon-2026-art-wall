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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .config import (EXAMPLE_GROUPS, EXAMPLES, EXAMPLES_DIR, FPS, FRAMES,
                     SUPPORTED_PACKAGES, Settings)

TEMPLATES_DIR = Path(__file__).parent / "templates"
# Committed page assets (the wall logo). Kept apart from the rendered-media
# mount, which serves untracked runtime state (ADR-0006).
STATIC_DIR = Path(__file__).parent / "static"


def _examples_for_page() -> dict:
    """The dropdown's contents, read off disk once at import.

    Delivered inline in the page rather than from an endpoint: it is a few
    kilobytes against a Pyodide boot that already pulls megabytes, and it
    means the switcher works before the runtime has finished loading.

    Split into the markup's part and the script's part. The `<select>` is
    rendered server-side so it is populated before any module script runs,
    and each option carries its index into `code`.
    """
    groups, index = [], 0
    for heading, count in EXAMPLE_GROUPS:
        entries = []
        for label_index in range(index, index + count):
            entries.append({"index": label_index,
                            "label": EXAMPLES[label_index][1]})
        groups.append({"heading": heading, "entries": entries})
        index += count
    if index != len(EXAMPLES):
        raise RuntimeError(
            f"EXAMPLE_GROUPS covers {index} of {len(EXAMPLES)} EXAMPLES")
    return {"groups": groups,
            "code": [(EXAMPLES_DIR / filename).read_text()
                     for filename, _ in EXAMPLES]}


EXAMPLES_FOR_PAGE = _examples_for_page()


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
    """Wall payload: the byline is the only credit that leaves the server.

    No contact name, no email, no code. An empty byline becomes null rather
    than a placeholder label, so an attendee who cleared it is unattributed.
    """
    return {
        "id": row["id"],
        "kind": row["kind"],
        "media_url": _media_url(row),
        "byline": row["byline"] or None,
    }


def _waited_for(since: str | None) -> str | None:
    """How long ago `since` was, phrased for a glance between conversations.

    None in, None out: with an empty queue the moderation page says nothing
    rather than something that reads like a stalled worker.
    """
    if since is None:
        return None
    started = datetime.fromisoformat(since)
    if started.tzinfo is None:                    # pre-tz rows, if any exist
        started = started.replace(tzinfo=timezone.utc)
    minutes = max(0, int(
        (datetime.now(timezone.utc) - started).total_seconds() // 60))
    if minutes < 1:
        return "under a minute"
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min"


@dataclass(frozen=True)
class ModerationState:
    """What the moderation page shows: its two grids, and its header."""
    pending: list           # rendered, awaiting the human review
    on_wall: list           # approved, and a takedown away from leaving
    counts: dict
    oldest_wait: str | None


def _read_moderation_state(conn) -> ModerationState:
    """Read what the moderation page shows, in one place.

    The page renders this and the open page's poll re-reads it, so which
    submissions belong in which grid cannot come out differently depending on
    which of the two asked.
    """
    counts = {status: 0 for status in db.STATUSES}
    for row in db.list_all(conn):
        counts[row["status"]] += 1
    return ModerationState(
        pending=db.list_by_status(conn, "rendered"),
        on_wall=db.list_by_status(conn, "approved"),
        counts=counts,
        oldest_wait=_waited_for(db.oldest_queued_at(conn)),
    )


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
            "examples": EXAMPLES_FOR_PAGE,
        })

    @app.get("/terms")
    def terms_page(request: Request):
        """Served by the application itself so consent survives the marketing
        site being unreachable, and travels with the booth-laptop fallback."""
        return templates.TemplateResponse(request, "terms.html", {})

    @app.get("/prompt")
    def prompt_page(request: Request):
        """The prompt for the booth laptop's AI assistant, served rather than
        linked for the same reason `terms_page` is: `docs/` is excluded from
        the images, so at the booth the documentation copy does not exist."""
        return templates.TemplateResponse(request, "prompt.html", {})

    @app.post("/submit")
    def submit(request: Request,
               code: str = Form(...),
               first_name: str = Form(...),
               last_name: str = Form(...),
               email: str = Form(...),
               byline: str = Form(""),
               phone: str = Form(""),
               company: str = Form(""),
               consent: bool = Form(False),
               conn=Depends(get_conn)):
        first_name, last_name = first_name.strip(), last_name.strip()
        if len(code.encode("utf-8")) > settings.max_code_bytes:
            raise HTTPException(413, "Code exceeds the 32 KB limit")
        if not code.strip() or not first_name or not last_name \
                or not email.strip():
            raise HTTPException(
                400, "Code, first name, last name and email are required")
        if not consent:
            raise HTTPException(400, "Consent is required")
        if db.count_queued(conn) >= settings.max_queue_depth:
            raise HTTPException(429, "Render queue is full — try again later")
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(ip):
            raise HTTPException(429, "Too many submissions — try again later")
        submission_id = db.create_submission(
            conn, code, db.compose_name(first_name, last_name), email.strip(),
            consent, byline.strip(), first_name=first_name,
            last_name=last_name, phone=phone.strip(), company=company.strip())
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
        state = _read_moderation_state(conn)
        return templates.TemplateResponse(request, "admin.html", {
            "pending": [dict(r) | {"media_url": _media_url(r)}
                        for r in state.pending],
            "on_wall": [dict(r) | {"media_url": _media_url(r)}
                        for r in state.on_wall],
            "counts": state.counts,
            "oldest_wait": state.oldest_wait,
        })

    @app.get("/admin/api/moderation", dependencies=[Depends(require_admin)])
    def moderation_json(conn=Depends(get_conn)):
        """What an open moderation page polls to notice it has gone stale.

        Ids rather than cards: drawing a card needs the server's markup, so the
        page reloads for that, and this reply is fetched every few seconds for
        as long as the booth is open.
        """
        state = _read_moderation_state(conn)
        return {
            "pending": [row["id"] for row in state.pending],
            "on_wall": [row["id"] for row in state.on_wall],
            "counts": state.counts,
            "oldest_wait": state.oldest_wait,
        }

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

    @app.post("/admin/submissions/{submission_id}/takedown",
              dependencies=[Depends(require_admin)])
    def takedown(submission_id: int, conn=Depends(get_conn)):
        db.take_down(conn, submission_id)
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin/export.csv", dependencies=[Depends(require_admin)])
    def export_csv(conn=Depends(get_conn)):
        buf = io.StringIO()
        writer = csv.writer(buf)
        # The first six columns are load-bearing for whoever reads this at the
        # booth; new columns append rather than reorder (see test_byline).
        writer.writerow(["id", "name", "email", "consent", "created_at",
                         "status", "byline", "first_name", "last_name",
                         "phone", "company"])
        for row in db.list_all(conn):
            writer.writerow([row["id"], row["name"], row["email"],
                             row["consent"], row["created_at"], row["status"],
                             row["byline"], row["first_name"],
                             row["last_name"], row["phone"], row["company"]])
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=submissions.csv"})

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
