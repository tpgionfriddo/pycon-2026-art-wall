"""SQLite access layer. The submissions table is also the render job queue
(ADR-0002): no broker, jobs survive restarts because the queue is the DB.

Status lifecycle: queued -> rendering -> rendered -> approved | rejected,
with failed reachable from rendering.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("queued", "rendering", "rendered", "approved", "rejected", "failed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    consent INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    kind TEXT,
    media_path TEXT,
    error TEXT,
    rendered_at TEXT,
    moderated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # server + worker share the file
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


def create_submission(conn, code: str, name: str, email: str, consent: bool) -> int:
    cur = conn.execute(
        "INSERT INTO submissions (code, name, email, consent, created_at, status)"
        " VALUES (?, ?, ?, ?, ?, 'queued')",
        (code, name, email, int(consent), utcnow()),
    )
    conn.commit()
    return cur.lastrowid


def get_submission(conn, submission_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()


def count_queued(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE status = 'queued'"
    ).fetchone()[0]


def claim_next_queued(conn) -> sqlite3.Row | None:
    """Atomically move the oldest queued submission to 'rendering'."""
    row = conn.execute(
        "UPDATE submissions SET status = 'rendering' WHERE id = ("
        "  SELECT id FROM submissions WHERE status = 'queued' ORDER BY id LIMIT 1"
        ") RETURNING *"
    ).fetchone()
    conn.commit()
    return row


def mark_rendered(conn, submission_id: int, kind: str, media_path: str) -> None:
    conn.execute(
        "UPDATE submissions SET status = 'rendered', kind = ?, media_path = ?,"
        " error = NULL, rendered_at = ? WHERE id = ?",
        (kind, media_path, utcnow(), submission_id),
    )
    conn.commit()


def mark_failed(conn, submission_id: int, error: str) -> None:
    conn.execute(
        "UPDATE submissions SET status = 'failed', error = ?, rendered_at = ?"
        " WHERE id = ?",
        (error, utcnow(), submission_id),
    )
    conn.commit()


def moderate(conn, submission_id: int, approved: bool) -> None:
    """Approve or reject a rendered submission."""
    conn.execute(
        "UPDATE submissions SET status = ?, moderated_at = ?"
        " WHERE id = ? AND status = 'rendered'",
        ("approved" if approved else "rejected", utcnow(), submission_id),
    )
    conn.commit()


def list_by_status(conn, status: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM submissions WHERE status = ? ORDER BY id", (status,)
    ).fetchall()


def list_all(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM submissions ORDER BY id").fetchall()


def requeue_stale_rendering(conn) -> int:
    """Return crashed-mid-render jobs to the queue (worker startup)."""
    cur = conn.execute(
        "UPDATE submissions SET status = 'queued' WHERE status = 'rendering'"
    )
    conn.commit()
    return cur.rowcount
