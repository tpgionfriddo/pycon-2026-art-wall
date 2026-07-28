"""Queue mechanics of the SQLite layer (ADR-0002)."""
from artwall import db


def _conn(tmp_path):
    return db.connect(tmp_path / "test.db")


def test_claim_is_fifo_and_exhausts(tmp_path):
    conn = _conn(tmp_path)
    a = db.create_submission(conn, "code-a", "A", "a@x", True)
    b = db.create_submission(conn, "code-b", "B", "b@x", True)

    first = db.claim_next_queued(conn)
    assert first["id"] == a
    assert first["status"] == "rendering"
    assert db.claim_next_queued(conn)["id"] == b
    assert db.claim_next_queued(conn) is None


def test_requeue_stale_rendering(tmp_path):
    conn = _conn(tmp_path)
    db.create_submission(conn, "c", "N", "n@x", True)
    db.claim_next_queued(conn)
    assert db.count_queued(conn) == 0
    assert db.requeue_stale_rendering(conn) == 1
    assert db.count_queued(conn) == 1
