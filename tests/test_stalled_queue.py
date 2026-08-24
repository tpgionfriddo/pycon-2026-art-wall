"""The stalled-queue signal: how long the oldest queued submission has waited.

The counts alone cannot tell a rush of submissions from a render worker that
died twenty minutes ago. The age can.
"""
from datetime import datetime, timedelta, timezone

from .conftest import AUTH, approved, submit


def _queued_since(conn, submission_id: int, minutes: int) -> None:
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    conn.execute("UPDATE submissions SET created_at = ? WHERE id = ?",
                 (when.isoformat(timespec="seconds"), submission_id))
    conn.commit()


def test_admin_reports_how_long_the_oldest_queued_submission_has_waited(
        client, conn):
    submit(client)
    _queued_since(conn, 1, minutes=25)
    body = client.get("/admin", auth=AUTH).text
    assert "oldest queued" in body
    assert "25 min" in body


def test_admin_reports_the_oldest_wait_not_the_newest(client, conn):
    submit(client)
    submit(client, first_name="Grace")
    _queued_since(conn, 1, minutes=40)
    _queued_since(conn, 2, minutes=3)
    body = client.get("/admin", auth=AUTH).text
    assert "40 min" in body
    assert "3 min" not in body


def test_a_long_wait_reads_in_hours(client, conn):
    submit(client)
    _queued_since(conn, 1, minutes=155)
    assert "2 h 35 min" in client.get("/admin", auth=AUTH).text


def test_a_fresh_submission_does_not_read_as_zero(client, conn):
    submit(client)
    body = client.get("/admin", auth=AUTH).text
    assert "oldest queued" in body
    assert "under a minute" in body


def test_nothing_is_reported_when_the_queue_is_empty(client, conn):
    assert "oldest queued" not in client.get("/admin", auth=AUTH).text

    # Submissions past the queue must not resurrect the signal either.
    approved(client, conn)
    assert "oldest queued" not in client.get("/admin", auth=AUTH).text
