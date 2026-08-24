"""The render worker's guards, without Docker (issue 03).

`test_pipeline.py` drives the same guards through real submission code, but
that whole module skips when the sandbox image is unavailable — and a guard
that only runs where Docker does is a guard that stops being checked.
"""
import json

import pytest

from artwall import db, worker
from artwall.config import Settings

CODE = "def draw():\n    return [[0]]\n"


@pytest.fixture
def env(tmp_path):
    settings = Settings(data_dir=tmp_path)
    conn = db.connect(settings.db_path)
    yield conn, settings
    conn.close()


def queue(conn, name: str = "Test") -> int:
    return db.create_submission(conn, CODE, name, "t@example.com", True)


@pytest.mark.parametrize("result,expected", [
    ({"kind": "sculpture", "media": "piece.png"}, "unknown kind"),
    ({"kind": None, "media": "piece.png"}, "unknown kind"),
    ({"kind": "static", "media": "../../etc/hostname"}, "expected 'piece.png'"),
    ({"kind": "static", "media": "/etc/hostname"}, "expected 'piece.png'"),
    ({"kind": "animated", "media": "piece.png"}, "expected 'piece.webm'"),
    ({"kind": "static"}, "expected 'piece.png'"),
])
def test_validate_media_rejects_what_the_harness_cannot_produce(result, expected):
    with pytest.raises(worker.RenderError, match=expected):
        worker.validate_media(result)


@pytest.mark.parametrize("result", [
    {"kind": "static", "media": "piece.png"},
    {"kind": "animated", "media": "piece.webm"},
])
def test_validate_media_accepts_the_harness_output(result):
    assert worker.validate_media(result) == (result["kind"], result["media"])


def write_result(out_dir, payload: str):
    (out_dir / "result.json").write_text(payload)


def test_read_result_reports_a_silent_sandbox(tmp_path):
    with pytest.raises(worker.RenderError, match="produced no result"):
        worker.read_result(tmp_path, "Traceback: boom")


@pytest.mark.parametrize("payload,expected", [
    ("{ not json at all", "unreadable"),
    ('"a string"', "not an object"),
    ("[]", "not an object"),
    ('{"error": "NameError: nope"}', "NameError: nope"),
    ('{"kind": "static", "media": "../../etc/hostname"}', "expected 'piece.png'"),
])
def test_read_result_rejects_a_hostile_result(tmp_path, payload, expected):
    write_result(tmp_path, payload)
    with pytest.raises(worker.RenderError, match=expected):
        worker.read_result(tmp_path, "")


def test_read_result_accepts_the_harness_output(tmp_path):
    write_result(tmp_path, json.dumps(
        {"kind": "animated", "media": "piece.webm", "error": None}))
    assert worker.read_result(tmp_path, "") == ("animated", "piece.webm")


def test_media_symlinked_out_of_the_sandbox_is_not_published(env, monkeypatch):
    conn, settings = env
    sid = queue(conn)

    def symlink_out(code, out_dir, *args, **kwargs):
        (out_dir / "piece.png").symlink_to("/etc/hostname")
        return "static", "piece.png"

    monkeypatch.setattr(worker, "run_container", symlink_out)
    assert worker.process_one(conn, settings) is True
    row = db.get_submission(conn, sid)
    assert row["status"] == "failed"
    assert "not a regular file" in row["error"]
    assert not settings.media_dir.exists()


def test_unexpected_failure_fails_only_that_submission(env, monkeypatch):
    conn, settings = env
    first, second = queue(conn), queue(conn)

    def explode(*args, **kwargs):
        raise ValueError("something nobody thought of")

    monkeypatch.setattr(worker, "run_container", explode)
    assert worker.process_one(conn, settings) is True
    row = db.get_submission(conn, first)
    assert row["status"] == "failed"
    assert "internal error" in row["error"]
    # the attendee sees this string on /submission/{id}: no host internals
    assert "ValueError" not in row["error"] and "/" not in row["error"]

    monkeypatch.undo()
    assert db.get_submission(conn, second)["status"] == "queued"


def test_loop_survives_a_failure_while_recording_a_failure(env, monkeypatch):
    conn, settings = env
    stuck, next_up = queue(conn), queue(conn)

    def explode(*args, **kwargs):
        raise ValueError("nope")

    monkeypatch.setattr(worker, "run_container", explode)
    monkeypatch.setattr(db, "mark_failed", explode)
    assert worker.poll_once(conn, settings) is False

    # left mid-render rather than requeued — skipped, not retried forever
    assert db.get_submission(conn, stuck)["status"] == "rendering"
    monkeypatch.undo()
    assert db.get_submission(conn, next_up)["status"] == "queued"
