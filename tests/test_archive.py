"""Archive: retiring a piece from the wall when the event moves on.

Distinct from a takedown throughout, and the difference is not cosmetic. A
takedown reverses a moderator's approval, so it is recorded as a moderation
decision and the piece stops resolving anywhere. An archive carries no
judgement about the piece at all: it only says the wall has moved on to a new
day, which is why it leaves the approval record alone.
"""
from artwall import db

from .conftest import AUTH, approved, every_status_but_approved


def test_approved_piece_can_be_archived(client, conn):
    sid = approved(client, conn)
    db.archive(conn, sid)
    assert db.get_submission(conn, sid)["status"] == "archived"


def _archive(client, sid: int, **kwargs):
    return client.post(f"/admin/submissions/{sid}/archive",
                       follow_redirects=False, **kwargs)


def test_archiving_a_piece_takes_it_off_the_wall(client, conn):
    sid = approved(client, conn)
    assert client.get("/api/wall").json()["pieces"] != []

    assert _archive(client, sid, auth=AUTH).status_code == 303
    assert db.get_submission(conn, sid)["status"] == "archived"
    assert client.get("/api/wall").json()["pieces"] == []


def test_archive_requires_the_moderator_password(client, conn):
    sid = approved(client, conn)
    assert _archive(client, sid).status_code == 401
    assert _archive(client, sid, auth=("booth", "wrong")).status_code == 401
    assert db.get_submission(conn, sid)["status"] == "approved"


def test_archive_is_reachable_only_from_approved(client, conn):
    """Every state an archive must refuse, in one pass.

    Shares its board of refused states with the takedown's version, in
    conftest. A piece the crowd never saw has nothing to retire from, and a
    queued or rendering submission is on its way to a moderator rather than on
    the wall.
    """
    before = every_status_but_approved(client, conn)
    for submission_id in before:
        assert _archive(client, submission_id, auth=AUTH).status_code == 303
    assert {r["id"]: r["status"] for r in db.list_all(conn)} == before


def test_archiving_a_removed_piece_changes_nothing(client, conn):
    """A takedown is not a route back to the wall, so it is not a route to the
    archive either. The record of what the crowd saw and what was pulled must
    survive the next day starting."""
    sid = approved(client, conn)
    db.take_down(conn, sid)
    _archive(client, sid, auth=AUTH)
    assert db.get_submission(conn, sid)["status"] == "removed"


def test_archiving_twice_changes_nothing(client, conn):
    sid = approved(client, conn)
    _archive(client, sid, auth=AUTH)
    _archive(client, sid, auth=AUTH)
    assert db.get_submission(conn, sid)["status"] == "archived"


def test_archiving_leaves_the_moderation_record_alone(client, conn):
    """The distinction from a takedown, asserted rather than described.

    `take_down` stamps `moderated_at` because it reverses a decision. An
    archive makes no decision about the piece, so the moment it was approved
    has to still be readable afterwards.
    """
    sid = approved(client, conn)
    approved_at = db.get_submission(conn, sid)["moderated_at"]
    assert approved_at is not None

    _archive(client, sid, auth=AUTH)
    assert db.get_submission(conn, sid)["moderated_at"] == approved_at
