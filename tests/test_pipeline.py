"""End-to-end render pipeline over the contract samples (MVP plan §6).

Needs Docker and the sandbox image:
    docker build -t artwall-worker -f worker/Dockerfile .
Skipped automatically when either is missing.
"""
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from artwall import db
from artwall.config import STATIC_BOX, VIDEO_BOX, Settings
from artwall.worker import process_one

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
IMAGE = "artwall-worker"

# every contract-compliant sample; py5_orbits.py is unsupported by design
SAMPLES = {
    "flow_field.py": "static",
    "circle_mosaic.py": "static",
    "adeptask_logo.py": "static",
    "plasma_shader.py": "animated",
    "torus_wireframe.py": "animated",
    "adeptask_logo_ish.py": "animated",
    "neon_cat.py": "animated",
    "stick_dance.py": "animated",
}


def _image_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "image", "inspect", IMAGE],
                          capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not _image_available(),
    reason="docker or the artwall-worker image is unavailable")


@pytest.fixture
def env(tmp_path):
    settings = Settings(data_dir=tmp_path, worker_image=IMAGE)
    conn = db.connect(settings.db_path)
    yield conn, settings
    conn.close()


def _render(conn, settings, code: str):
    sid = db.create_submission(conn, code, "Test", "t@example.com", True)
    assert process_one(conn, settings) is True
    return db.get_submission(conn, sid)


def _probe_video(path: Path) -> tuple[str, int, int, str]:
    """codec/width/height/alpha_mode via ffprobe inside the worker image
    (host has none)."""
    out = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{path}:/probe.webm:ro", IMAGE,
         "ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height:stream_tags=alpha_mode",
         "-of", "default=nw=1", "/probe.webm"],
        capture_output=True, text=True, check=True).stdout.strip()
    info = dict(line.split("=", 1) for line in out.splitlines())
    return (info["codec_name"], int(info["width"]), int(info["height"]),
            info.get("TAG:alpha_mode", "0"))


@pytest.mark.parametrize("sample,kind", SAMPLES.items())
def test_sample_renders(env, sample, kind):
    conn, settings = env
    row = _render(conn, settings, (SAMPLES_DIR / sample).read_text())

    assert row["status"] == "rendered", row["error"]
    assert row["kind"] == kind
    media = settings.media_dir / row["media_path"]
    assert media.exists()

    if kind == "static":
        assert media.suffix == ".png"
        with Image.open(media) as img:
            assert img.format == "PNG"
            assert img.width <= STATIC_BOX and img.height <= STATIC_BOX
            assert img.mode == "RGBA"
            # every static sample leaves its corners unpainted
            assert img.getpixel((0, 0))[3] == 0
    else:
        assert media.suffix == ".webm"
        codec, w, h, alpha_mode = _probe_video(media)
        assert codec == "vp9"
        assert w <= VIDEO_BOX and h <= VIDEO_BOX
        assert alpha_mode == "1"  # VP9 alpha channel present


def test_broken_code_marks_failed(env):
    conn, settings = env
    row = _render(conn, settings, "import numpy as np\nnope()\n")
    assert row["status"] == "failed"
    assert "NameError" in row["error"]


def test_missing_draw_marks_failed(env):
    conn, settings = env
    row = _render(conn, settings, "x = 42\n")
    assert row["status"] == "failed"
    assert "must define draw" in row["error"]


def test_infinite_loop_killed_from_host(env):
    conn, settings = env
    settings.render_timeout_s = 15
    row = _render(conn, settings, "while True:\n    pass\n")
    assert row["status"] == "failed"
    assert "killed" in row["error"]


# --- hostile submissions (issue 03) ------------------------------------

TRIVIAL_DRAW = "def draw():\n    return [[0]]\n"


def _hijack_result(payload: str) -> str:
    """Submission code that hands the host `payload` as its sandbox result.

    The harness writes result.json as it finishes, so the overwrite has to
    happen on the way out — after main() has had the last word.
    """
    return (f"import atexit, pathlib\n"
            f"atexit.register(lambda: "
            f"pathlib.Path('/out/result.json').write_text({payload!r}))\n"
            + TRIVIAL_DRAW)


MALFORMED_RESULT = _hijack_result("{ not json at all")
PATH_ESCAPE_RESULT = _hijack_result('{"kind": "static", "media": "/etc/hostname"}')


def test_malformed_result_marks_failed(env):
    conn, settings = env
    row = _render(conn, settings, MALFORMED_RESULT)
    assert row["status"] == "failed"
    assert "unreadable" in row["error"]
    assert row["media_path"] is None


def test_result_naming_a_path_outside_the_sandbox_moves_nothing(env):
    conn, settings = env
    escape = '{"kind": "static", "media": "../../../../etc/hostname"}'
    row = _render(conn, settings, _hijack_result(escape))
    assert row["status"] == "failed"
    assert "expected 'piece.png'" in row["error"]
    assert row["media_path"] is None
    assert not settings.media_dir.exists() or not any(settings.media_dir.iterdir())


@pytest.mark.parametrize("hostile", [MALFORMED_RESULT, PATH_ESCAPE_RESULT],
                         ids=["malformed", "path-escape"])
def test_queue_keeps_moving_after_a_hostile_submission(env, hostile):
    conn, settings = env
    assert _render(conn, settings, hostile)["status"] == "failed"
    assert _render(conn, settings, TRIVIAL_DRAW)["status"] == "rendered"


def test_job_container_drops_capabilities_and_privilege_escalation(env):
    conn, settings = env
    probe = (
        "import re\n"
        "from pathlib import Path\n"
        "status = Path('/proc/self/status').read_text()\n"
        "caps = re.search(r'^CapEff:\\s+(\\S+)', status, re.M).group(1)\n"
        "nnp = re.search(r'^NoNewPrivs:\\s+(\\S+)', status, re.M).group(1)\n"
        "assert int(caps, 16) == 0, f'CapEff={caps}'\n"
        "assert nnp == '1', f'NoNewPrivs={nnp}'\n"
        + TRIVIAL_DRAW
    )
    assert _render(conn, settings, probe)["status"] == "rendered"


def test_media_symlinked_out_of_the_sandbox_is_not_published(env):
    """The result may name only `piece.png` — but the file behind that name
    is the submission's to create, and it can be a symlink to a host file."""
    conn, settings = env
    row = _render(conn, settings, (
        "import atexit, os, pathlib\n"
        "def hijack():\n"
        "    p = pathlib.Path('/out/piece.png')\n"
        "    if p.exists() or p.is_symlink():\n"
        "        p.unlink()\n"
        "    os.symlink('/etc/hostname', '/out/piece.png')\n"
        "atexit.register(hijack)\n"
        + TRIVIAL_DRAW
    ))
    assert row["status"] == "failed"
    assert "not a regular file" in row["error"]
    assert row["media_path"] is None
    assert not settings.media_dir.exists() or not any(settings.media_dir.iterdir())


# --- configurable scratch area (issue 04) ------------------------------

def test_render_from_a_configured_scratch_base(env, tmp_path):
    """The whole pipeline again with the scratch base set rather than
    defaulting: the mounts the daemon resolves come out of that base, and the
    per-job directories are gone afterwards."""
    conn, settings = env
    base = tmp_path / "scratch"
    base.mkdir()
    settings.scratch_dir = base

    row = _render(conn, settings, (SAMPLES_DIR / "flow_field.py").read_text())

    assert row["status"] == "rendered", row["error"]
    assert (settings.media_dir / row["media_path"]).exists()
    assert list(base.iterdir()) == []
