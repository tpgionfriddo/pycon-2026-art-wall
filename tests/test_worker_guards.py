"""The render worker's guards, without Docker (issue 03).

`test_pipeline.py` drives the same guards through real submission code, but
that whole module skips when the sandbox image is unavailable — and a guard
that only runs where Docker does is a guard that stops being checked.
"""
import json
import subprocess
import tempfile
from pathlib import Path

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


# --- configurable scratch area (issue 04) ------------------------------

class FakeDockerRun:
    """Stand-in for `docker run`, recording the bind-mount sources it is
    given — those are what the Docker daemon resolves on the host, so they
    are what a containerised worker has to get right."""

    def __init__(self):
        self.source: Path | None = None
        self.out_dir: Path | None = None

    def __call__(self, cmd, **kwargs):
        self.source, self.out_dir = [
            Path(cmd[i + 1].split(":")[0])
            for i, arg in enumerate(cmd) if arg == "-v"
        ]
        (self.out_dir / "piece.png").write_bytes(b"not really a png")
        (self.out_dir / "result.json").write_text(
            json.dumps({"kind": "static", "media": "piece.png"}))
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture
def fake_docker(monkeypatch) -> FakeDockerRun:
    fake = FakeDockerRun()
    monkeypatch.setattr(worker.subprocess, "run", fake)
    return fake


def test_scratch_paths_live_under_a_configured_base(env, fake_docker, tmp_path):
    conn, settings = env
    base = tmp_path / "scratch"
    base.mkdir()
    settings.scratch_dir = base
    queue(conn)

    assert worker.process_one(conn, settings) is True

    assert base in fake_docker.source.parents, fake_docker.source
    assert base in fake_docker.out_dir.parents, fake_docker.out_dir
    assert list(base.iterdir()) == []    # per-job scratch cleaned up


def test_scratch_defaults_to_the_system_temporary_directory(env, fake_docker):
    conn, settings = env                 # scratch_dir left unset
    queue(conn)

    assert worker.process_one(conn, settings) is True

    system_tmp = Path(tempfile.gettempdir()).resolve()
    for path in (fake_docker.source, fake_docker.out_dir):
        assert system_tmp in path.resolve().parents, path


def test_scratch_base_is_configured_through_the_environment(monkeypatch):
    monkeypatch.delenv("ARTWALL_SCRATCH_DIR", raising=False)
    assert Settings.from_env().scratch_dir is None

    monkeypatch.setenv("ARTWALL_SCRATCH_DIR", "/srv/artwall/scratch")
    assert Settings.from_env().scratch_dir == Path("/srv/artwall/scratch")


def test_a_base_the_daemon_would_misread_stops_the_worker(tmp_path):
    """A relative base is a named volume to the daemon, and an absolute one
    it cannot find on the host is created there empty and mounted over the
    submission. Both have to be refused before any attendee pays for it."""
    with pytest.raises(worker.ScratchBaseError, match="named volume"):
        worker.check_scratch_base(Settings(scratch_dir=Path("scratch")))

    missing = tmp_path / "never-mounted"
    with pytest.raises(worker.ScratchBaseError, match="not a directory"):
        worker.check_scratch_base(Settings(scratch_dir=missing))


def test_an_absent_or_mounted_base_is_accepted(tmp_path):
    assert worker.check_scratch_base(Settings()) is None
    assert worker.check_scratch_base(Settings(scratch_dir=tmp_path)) is None


def _docker_argv(monkeypatch, settings) -> list[str]:
    """The argv `run_container` hands Docker, without running it."""
    seen = {}

    class Done:
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        # Enough of a result for read_result to succeed.
        out = Path(cmd[cmd.index("-v", cmd.index("-v") + 1) + 1].split(":")[0])
        (out / "result.json").write_text(
            json.dumps({"kind": "static", "media": "piece.png"}))
        (out / "piece.png").write_bytes(b"")
        return Done()

    monkeypatch.setattr(subprocess, "run", fake_run)
    with tempfile.TemporaryDirectory() as td:
        worker.run_container(CODE, Path(td), settings, 1)
    return seen["cmd"], seen["kwargs"]


def test_the_render_gets_the_configured_cpu_allowance(monkeypatch, tmp_path):
    """Animated pieces draw in Python while ffmpeg encodes, two processes
    through a pipe, so a one-CPU cap serialises work that could overlap.
    Measured: the slowest Example goes from 15.1 s to 7.1 s at two CPUs and
    barely moves at three. The worker renders one job at a time, so this
    allowance is the most rendering can ever take from the host.
    """
    settings = Settings(data_dir=tmp_path, render_cpus=2.0)
    cmd, _ = _docker_argv(monkeypatch, settings)
    assert "--cpus" in cmd
    assert cmd[cmd.index("--cpus") + 1] == "2.0"
    assert cmd.count("--cpus") == 1, "one allowance, not two competing ones"


def test_the_other_sandbox_guards_survive_a_tunable_cpu_allowance(monkeypatch, tmp_path):
    """The CPU allowance moved out of the flag constant to become tunable.
    Nothing else may have moved with it: these are what make the sandbox one.
    """
    cmd, kwargs = _docker_argv(monkeypatch, Settings(data_dir=tmp_path))
    for flag, value in (("--network", "none"), ("--memory", "1g"),
                        ("--pids-limit", "128"), ("--cap-drop", "ALL"),
                        ("--security-opt", "no-new-privileges")):
        assert flag in cmd, flag
        assert cmd[cmd.index(flag) + 1] == value, flag
    assert kwargs.get("timeout") == Settings().render_timeout_s
