"""Takedown: pulling an approved piece back off the wall.

Distinct from a rejection throughout — a rejected submission was never seen
by anyone, and afterwards it matters which is which.
"""
from artwall import db

from .conftest import AUTH, approved, rendered, submit


def _takedown(client, sid: int, **kwargs):
    return client.post(f"/admin/submissions/{sid}/takedown",
                       follow_redirects=False, **kwargs)


def test_approved_piece_can_be_taken_off_the_wall(client, conn):
    sid = approved(client, conn)
    assert client.get("/api/wall").json()["pieces"] != []

    assert _takedown(client, sid, auth=AUTH).status_code == 303
    assert db.get_submission(conn, sid)["status"] == "removed"
    assert client.get("/api/wall").json()["pieces"] == []


def test_takedown_is_recorded_distinctly_from_a_rejection(client, conn):
    taken_down = approved(client, conn)
    rejected = rendered(client, conn, name="Grace")
    db.moderate(conn, rejected, approved=False)
    _takedown(client, taken_down, auth=AUTH)

    assert db.get_submission(conn, taken_down)["status"] == "removed"
    assert db.get_submission(conn, rejected)["status"] == "rejected"


def test_taken_down_piece_page_stops_resolving(client, conn):
    sid = approved(client, conn)
    assert client.get(f"/piece/{sid}").status_code == 200
    _takedown(client, sid, auth=AUTH)
    assert client.get(f"/piece/{sid}").status_code == 404


def test_takedown_is_reachable_only_from_approved(client, conn):
    """Every state a takedown must refuse, in one pass."""
    rendered(client, conn)                                          # 1
    db.mark_failed(conn, rendered(client, conn, name="Grace"), "!")  # 2
    db.moderate(conn, rendered(client, conn, name="Mary"), approved=False)  # 3
    db.create_submission(conn, "c", "Alan", "alan@x", True)          # 4
    db.claim_next_queued(conn)                                       # -> rendering
    submit(client, name="Edsger")                                    # 5, queued

    before = {r["id"]: r["status"] for r in db.list_all(conn)}
    assert set(before.values()) == {"rendered", "failed", "rejected",
                                    "rendering", "queued"}
    for submission_id in before:
        assert _takedown(client, submission_id, auth=AUTH).status_code == 303
    assert {r["id"]: r["status"] for r in db.list_all(conn)} == before


def test_takedown_of_an_already_removed_piece_changes_nothing(client, conn):
    sid = approved(client, conn)
    _takedown(client, sid, auth=AUTH)
    moderated_at = db.get_submission(conn, sid)["moderated_at"]
    _takedown(client, sid, auth=AUTH)
    row = db.get_submission(conn, sid)
    assert row["status"] == "removed"
    assert row["moderated_at"] == moderated_at


def test_takedown_requires_the_moderator_password(client, conn):
    sid = approved(client, conn)
    assert _takedown(client, sid).status_code == 401
    assert _takedown(client, sid, auth=("booth", "wrong")).status_code == 401
    assert db.get_submission(conn, sid)["status"] == "approved"


def test_taken_down_submissions_stay_in_the_csv_export(client, conn):
    sid = approved(client, conn, name="Grace", email="grace@example.com")
    _takedown(client, sid, auth=AUTH)
    body = client.get("/admin/export.csv", auth=AUTH).text
    assert "grace@example.com" in body
    assert "removed" in body


def test_moderation_queue_offers_takedown_for_pieces_on_the_wall(client, conn):
    sid = approved(client, conn)
    body = client.get("/admin", auth=AUTH).text
    assert f"/admin/submissions/{sid}/takedown" in body
    _takedown(client, sid, auth=AUTH)
    assert f"/admin/submissions/{sid}/takedown" not in client.get(
        "/admin", auth=AUTH).text


def test_status_page_tells_the_attendee_their_piece_was_taken_down(client, conn):
    submission_id = approved(client, conn)
    _takedown(client, submission_id, auth=AUTH)
    body = client.get(f"/api/submission/{submission_id}").json()
    assert body["status"] == "removed"
    assert "taken down" in client.get(f"/submission/{submission_id}").text
