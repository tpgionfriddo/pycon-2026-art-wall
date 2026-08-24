"""The wall's logo is a committed asset, not runtime state.

The rendered-media mount serves the untracked data directory, so a wall that
loaded its logo from there showed a broken image anywhere but the laptop that
rendered it. The asset is committed and served from its own mount instead
(ADR-0006's amendment), which has to hold from a fresh clone whose data
directory is still empty.
"""
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urljoin

import pytest

from artwall.server import STATIC_DIR

LOGO = STATIC_DIR / "PyCharm-white.svg"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _logo_url(client) -> str:
    """The logo URL the wall page actually asks the browser for."""
    html = client.get("/wall").text
    tag = re.search(r"<img[^>]*\bid=\"logo\"[^>]*>", html)
    assert tag, 'the wall page has no <img id="logo">'
    src = re.search(r'\bsrc="([^"]+)"', tag.group())
    assert src, f"the wall logo has no src: {tag.group()}"
    return urljoin("/wall", src.group(1))


def test_logo_is_tracked_by_git():
    """A fresh clone must carry the asset — existing on this laptop isn't it."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", LOGO.relative_to(REPO_ROOT)],
        cwd=REPO_ROOT, capture_output=True)
    assert tracked.returncode == 0, f"{LOGO} is not in version control"


def test_wall_logo_renders_with_an_empty_data_dir(client):
    """The acceptance test: fresh clone, nothing rendered yet."""
    assert list(client.settings.media_dir.iterdir()) == []

    resp = client.get(_logo_url(client))

    assert resp.status_code == 200
    assert "<svg" in resp.text


def test_wall_logo_does_not_come_from_the_media_mount(client):
    assert not _logo_url(client).startswith("/media/")
