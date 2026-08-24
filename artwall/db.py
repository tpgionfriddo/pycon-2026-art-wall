"""SQLite access layer. The submissions table is also the render job queue
(ADR-0002): no broker, jobs survive restarts because the queue is the DB.

Status lifecycle: queued -> rendering -> rendered -> approved | rejected,
with failed reachable from rendering, and removed (a takedown) reachable from
approved. A rejected submission was never displayed; a removed one was.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("queued", "rendering", "rendered", "approved", "rejected",
            "removed", "failed")

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
    moderated_at TEXT,
    -- Declared last, in the order _add_missing_columns() appends them, so a
    -- fresh database matches one migrated by it. It can only append.
    byline TEXT NOT NULL DEFAULT '',
    -- `name` above stays the composed full name, because the status page, the
    -- admin list and the CSV export all show it. These keep the parts the form
    -- actually collected, and are empty for rows written before the split.
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
"""

# Every column added after the first release, in the order SCHEMA declares
# them at the end of the table. _add_missing_columns() appends in this order,
# which is what keeps a migrated database identical to a fresh one — see
# tests/test_contact_fields.py::test_a_migrated_database_matches_a_fresh_one.
APPENDED_COLUMNS = ("byline", "first_name", "last_name", "phone", "company")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compose_name(first_name: str, last_name: str) -> str:
    """The full contact name, from the two fields the form collects.

    One definition, so the composed `name` column can never disagree with the
    parts stored beside it. A missing half yields no stray space.
    """
    return " ".join(p for p in (first_name.strip(), last_name.strip()) if p)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # server + worker share the file
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn) -> None:
    """Bring a database written by an older build up to SCHEMA, on connect,
    so there is no separate migration step to forget at the booth."""
    present = {r["name"] for r in conn.execute("PRAGMA table_info(submissions)")}
    for column in APPENDED_COLUMNS:
        if column not in present:
            # Identifiers cannot be bound, and APPENDED_COLUMNS is a literal
            # no caller reaches, so the interpolation is safe.
            conn.execute(f"ALTER TABLE submissions ADD COLUMN {column}"
                         " TEXT NOT NULL DEFAULT ''")
    conn.commit()


def create_submission(conn, code: str, name: str, email: str, consent: bool,
                      byline: str = "", first_name: str = "",
                      last_name: str = "", phone: str = "",
                      company: str = "") -> int:
    """`byline` is the public credit; empty means displayed unattributed.

    `name` is the composed full name and stays required. `first_name` and
    `last_name` are the parts it was composed from, and `phone` and `company`
    are optional, so all four default to empty for a caller that has only a
    whole name to give.
    """
    cur = conn.execute(
        "INSERT INTO submissions (code, name, email, consent, byline,"
        " first_name, last_name, phone, company, created_at, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')",
        (code, name, email, int(consent), byline, first_name, last_name,
         phone, company, utcnow()),
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


def oldest_queued_at(conn) -> str | None:
    """When the longest-waiting queued submission arrived, or None if the
    queue is empty. A queue that is not moving shows up here as an old
    timestamp while the counts alone would look like an ordinary rush."""
    row = conn.execute(
        "SELECT created_at FROM submissions WHERE status = 'queued'"
        " ORDER BY id LIMIT 1"          # the row claim_next_queued takes next
    ).fetchone()
    return row["created_at"] if row else None


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


def take_down(conn, submission_id: int) -> None:
    """Pull an approved piece off the wall.

    Only from 'approved' — a takedown is the removal of something the crowd
    has already seen, which is why it is not just another rejection.
    """
    conn.execute(
        "UPDATE submissions SET status = 'removed', moderated_at = ?"
        " WHERE id = ? AND status = 'approved'",
        (utcnow(), submission_id),
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
