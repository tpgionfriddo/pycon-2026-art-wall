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
    "plasma_shader.py": "animated",
    "torus_wireframe.py": "animated",
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


def _probe_video(path: Path) -> tuple[str, int, int]:
    """codec/width/height via ffprobe inside the worker image (host has none)."""
    out = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{path}:/probe.webm:ro", IMAGE,
         "ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height",
         "-of", "csv=p=0", "/probe.webm"],
        capture_output=True, text=True, check=True).stdout.strip()
    codec, w, h = out.split(",")
    return codec, int(w), int(h)


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
    else:
        assert media.suffix == ".webm"
        codec, w, h = _probe_video(media)
        assert codec == "vp9"
        assert w <= VIDEO_BOX and h <= VIDEO_BOX


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
