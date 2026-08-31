"""The gallery export and the static site built from it.

Two things are load-bearing here and neither is visual. The export must carry
no contact info, because a public website is generated verbatim out of it.
And it must carry the archived pieces, because those are the days of the
event the wall no longer shows — leaving them out silently publishes the last
day and calls it the gallery.
"""
import json
import shutil
import subprocess

import pytest

from artwall import db, gallery
from .conftest import AUTH, approved, rendered, submit

EXPORT = "/admin/export/gallery.json"

# What the CSV export exists to carry and this one must not.
CONTACT_FIELDS = ("name", "email", "first_name", "last_name", "phone",
                  "company")


def archived(client, conn, **overrides) -> int:
    """A piece that was on the wall on an earlier day of the event."""
    submission_id = approved(client, conn, **overrides)
    db.archive(conn, submission_id)
    return submission_id


# ---- the export ----------------------------------------------------------

def test_export_needs_the_moderator_password(client):
    assert client.get(EXPORT).status_code == 401


def test_export_carries_approved_and_archived_pieces(client, conn):
    on_wall = approved(client, conn)
    earlier_day = archived(client, conn, first_name="Grace")

    pieces = client.get(EXPORT, auth=AUTH).json()["pieces"]

    assert [p["id"] for p in pieces] == [on_wall, earlier_day]


def test_export_omits_everything_a_moderator_did_not_pass(client, conn):
    """A takedown is not an archive, and neither is a rejection.

    The three states that mean 'not on the wall' arrive at that answer for
    different reasons, and only one of them is the event moving on.
    """
    taken_down = approved(client, conn)
    db.take_down(conn, taken_down)
    db.moderate(conn, rendered(client, conn, first_name="Mary"), approved=False)
    db.mark_failed(conn, rendered(client, conn, first_name="Alan"), "boom")
    rendered(client, conn, first_name="Edsger")        # awaiting moderation
    submit(client, first_name="Ada")                   # still queued
    kept = archived(client, conn, first_name="Grace")

    pieces = client.get(EXPORT, auth=AUTH).json()["pieces"]

    assert [p["id"] for p in pieces] == [kept]


def test_export_carries_no_contact_info(client, conn):
    """The one guard that matters: this payload becomes a public website.

    The byline is given here rather than left at the form's default, which
    mirrors the contact name: an attendee is free to make their byline their
    own full name, and then the surname below appears legitimately and this
    test proves nothing.
    """
    approved(client, conn, byline="ada")

    body = client.get(EXPORT, auth=AUTH)

    for field in CONTACT_FIELDS:
        assert field not in body.json()["pieces"][0]
    # Not just absent under those keys — absent from the payload entirely,
    # so a field smuggled in under another name still fails here.
    assert "ada@example.com" not in body.text
    assert "Lovelace" not in body.text


def test_export_carries_the_code_and_the_byline(client, conn):
    approved(client, conn, byline="Ada", code="def draw():\n    return [[7]]\n")

    piece = client.get(EXPORT, auth=AUTH).json()["pieces"][0]

    assert piece["byline"] == "Ada"
    assert "[[7]]" in piece["code"]
    assert piece["kind"] == "static"
    assert piece["media_path"].endswith(".png")


def test_a_cleared_byline_exports_as_null_not_a_placeholder(client, conn):
    approved(client, conn, byline="")

    assert client.get(EXPORT, auth=AUTH).json()["pieces"][0]["byline"] is None


# ---- the generated site --------------------------------------------------

@pytest.fixture
def site(tmp_path, client, conn, monkeypatch):
    """Build a real gallery out of a real server, over the test transport."""
    def make(pieces=(("Ada", "static"), ("Grace", "animated")), **kwargs):
        for byline, kind in pieces:
            submission_id = rendered(client, conn, byline=byline)
            suffix = "webm" if kind == "animated" else "png"
            db.mark_rendered(conn, submission_id, kind,
                             f"{submission_id}.{suffix}")
            db.moderate(conn, submission_id, approved=True)
            (client.settings.media_dir / f"{submission_id}.{suffix}"
             ).write_bytes(b"not really a render, and nothing reads it")

        # urllib is what the generator uses in the field; here it has to
        # reach an app that is not on a socket, so the one seam between the
        # two is redirected at the TestClient.
        def fake_get(url, password):
            path = url.replace("https://wall.example", "")
            response = client.get(path, auth=AUTH if password else None)
            assert response.status_code == 200, f"{path} -> {response.status_code}"
            return response.content

        monkeypatch.setattr(gallery, "_get", fake_get)
        out = tmp_path / "site"
        gallery.build("https://wall.example", "hunter2", out,
                      kwargs.pop("winner_ids", []), kwargs.pop("exclude", set()),
                      "Code Art Wall", "subtitle", log=lambda *a: None)
        return out
    return make


def test_the_site_is_one_page_plus_its_media(site):
    out = site()

    assert (out / "index.html").exists()
    assert (out / ".nojekyll").exists()
    assert sorted(p.suffix for p in (out / "media").iterdir()) == [".png",
                                                                  ".webm"]


def test_every_piece_gets_a_tile_and_its_source(site):
    out = site()
    page = (out / "index.html").read_text()

    assert page.count('class="tile"') == 2
    assert "Ada" in page and "Grace" in page
    # The code is highlighted at build time, so the published page needs
    # nothing from a CDN to show it.
    assert 'class="hl"' in page
    assert "draw" in page


def test_without_winners_no_piece_wears_a_trophy(site):
    assert 'class="trophy"' not in (site() / "index.html").read_text()


def test_a_winner_keeps_its_place_and_wears_a_trophy(site):
    """The winner is not lifted out of the grid, only marked inside it."""
    page = (site(winner_ids=[1]) / "index.html").read_text()

    assert page.count('class="tile"') == 2          # still one tile per piece
    assert page.count('class="trophy"') == 1
    assert 'title="Day 1 winner"' in page


def test_each_winner_gets_its_own_day_number(site):
    page = (site(winner_ids=[2, 1]) / "index.html").read_text()

    assert 'title="Day 1 winner"' in page           # the id given first
    assert 'title="Day 2 winner"' in page
    assert page.count('class="trophy"') == 2


def test_the_trophy_is_drawn_in_the_page_rather_than_fetched(site):
    """One file plus its media: nothing here may reach for a second asset."""
    page = (site(winner_ids=[1]) / "index.html").read_text()

    assert "<svg" in page
    assert "shape-rendering" in page


def test_the_day_number_changes_the_trophy(site):
    assert gallery.trophy_svg(1) != gallery.trophy_svg(2)


def test_a_two_digit_day_still_gets_a_trophy(site):
    """The cup is three pixels wide, so eleven loses its number, not its cup."""
    assert "<svg" in gallery.trophy_svg(11)


def test_a_winner_that_is_not_in_the_export_is_an_error(site):
    with pytest.raises(gallery.GalleryError, match="99"):
        site(winner_ids=[99])


def test_excluded_pieces_do_not_reach_the_site(site):
    out = site(exclude={1})
    page = (out / "index.html").read_text()

    assert page.count('class="tile"') == 1
    assert "Ada" not in page
    assert not (out / "media" / "1.png").exists()


def test_a_removed_tile_closes_the_grid_up_behind_it(site):
    """Deleting a media file from the published repository is how a piece is
    pulled, so the tile must not leave its slot behind as a hole. The tile is
    `display: block`, which outranks the browser's own rule for [hidden]."""
    page = (site() / "index.html").read_text()

    assert ".tile[hidden] { display: none; }" in page


# ---- the still every animated piece needs --------------------------------

def _webm(path, seconds=1):
    """A tiny real VP9 loop, so ffmpeg has something true to read."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc=size=64x64:rate=10:duration={seconds}",
         "-c:v", "libvpx-vp9", "-b:v", "50k", str(path)],
        check=True, capture_output=True, timeout=120)


needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="poster extraction needs ffmpeg")


@needs_ffmpeg
def test_an_animated_piece_gets_a_still_beside_its_media(tmp_path):
    """A <video> with no poster paints nothing until it decodes a frame, so
    without this the grid opens as a page of empty boxes."""
    media = tmp_path / "media"
    media.mkdir()
    _webm(media / "3.webm")
    pieces = [{"id": 3, "kind": "animated", "media_path": "3.webm"}]

    out = gallery.build_posters(pieces, media, log=lambda *a: None)

    assert out[0]["poster_url"] == "media/3.poster.jpg"
    assert (media / "3.poster.jpg").exists()


@needs_ffmpeg
def test_the_still_sits_beside_the_media_it_belongs_to(tmp_path):
    """Removal from the published gallery is `rm media/3.*` and nothing else,
    so the two files have to share a stem."""
    media = tmp_path / "media"
    media.mkdir()
    _webm(media / "3.webm")

    gallery.build_posters([{"id": 3, "kind": "animated",
                            "media_path": "3.webm"}], media,
                          log=lambda *a: None)

    assert sorted(p.name for p in media.iterdir()) == ["3.poster.jpg",
                                                       "3.webm"]


def test_a_static_piece_needs_no_still(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    pieces = [{"id": 3, "kind": "static", "media_path": "3.png"}]

    assert gallery.build_posters(pieces, media, log=lambda *a: None) == pieces


def test_without_ffmpeg_the_build_carries_on_and_says_so(tmp_path,
                                                         monkeypatch):
    """Losing the stills is a visible downgrade, not a failed build."""
    monkeypatch.setattr(gallery, "_ffmpeg_available", lambda: False)
    said = []
    pieces = [{"id": 3, "kind": "animated", "media_path": "3.webm"}]

    out = gallery.build_posters(pieces, tmp_path, log=said.append)

    assert out == pieces                      # unchanged; no poster_url
    assert any("ffmpeg" in line for line in said)


def test_a_grid_tile_shows_the_still_and_names_its_video(site):
    """The tile is an image; the video is hung on it only while on screen."""
    page = gallery.render_page(
        [{"id": 3, "kind": "animated", "media_url": "media/3.webm",
          "poster_url": "media/3.poster.jpg", "byline": "Ada",
          "code": "x = 1\n"}], [], "t", "s")

    assert 'src="media/3.poster.jpg"' in page
    assert 'data-video="media/3.webm"' in page
    assert "<video" not in page.split("</style>")[1].split("<script")[0]


def test_without_a_still_the_tile_falls_back_to_a_video(site):
    page = gallery.render_page(
        [{"id": 3, "kind": "animated", "media_url": "media/3.webm",
          "poster_url": None, "byline": "Ada", "code": "x = 1\n"}],
        [], "t", "s")

    assert '<video src="media/3.webm"' in page


def test_a_piece_whose_media_will_not_download_is_dropped(tmp_path,
                                                          monkeypatch):
    """One unreadable render must not cost the rest of the gallery."""
    def flaky(url, password):
        if url.endswith("2.png"):
            raise gallery.GalleryError("410 Gone")
        return b"bytes"

    monkeypatch.setattr(gallery, "_get", flaky)
    pieces = [{"id": 1, "media_path": "1.png"}, {"id": 2, "media_path": "2.png"}]

    kept = gallery.download_media("https://wall.example", pieces,
                                  tmp_path / "media", log=lambda *a: None)

    assert [p["id"] for p in kept] == [1]


def test_a_rebuild_does_not_refetch_media_it_already_has(tmp_path, monkeypatch):
    fetched = []

    def counting(url, password):
        fetched.append(url)
        return b"bytes"

    monkeypatch.setattr(gallery, "_get", counting)
    pieces = [{"id": 1, "media_path": "1.png"}]
    for _ in range(2):
        gallery.download_media("https://wall.example", pieces,
                               tmp_path / "media", log=lambda *a: None)

    assert len(fetched) == 1
