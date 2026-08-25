"""The wall carries the invitation: a QR code and the Submit URL under it.

The booth TV is the only invitation most attendees get, and the address it
sends them to is deliberately not this stack's own — a short link on a domain
the booth owns, redirected at the public URL, so a moved stack costs a
redirect rather than a reprint (ADR-0004's second amendment). That makes the
address configuration, and everything below is about it being the configured
one, readable off the screen, and not sitting on top of the pieces (ADR-0005).
"""
import re
import xml.etree.ElementTree as ET

import segno

from artwall.config import Settings
from artwall.server import qr_svg

DEFAULT_URL = "go.adeptask.com/pycon26"


def _qr_url(client) -> str:
    """The QR image URL the wall page actually asks the browser for."""
    html = client.get("/wall").text
    tag = re.search(r"<img[^>]*\bid=\"qr\"[^>]*>", html)
    assert tag, 'the wall page has no <img id="qr">'
    src = re.search(r'\bsrc="([^"]+)"', tag.group())
    assert src, f"the wall QR has no src: {tag.group()}"
    return src.group(1)


def test_wall_shows_the_qr_and_the_url_below_it(client):
    html = client.get("/wall").text

    assert _qr_url(client)
    assert DEFAULT_URL in html


def test_qr_encodes_the_submission_url_over_https(client):
    resp = client.get(_qr_url(client))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.text == qr_svg(f"https://{DEFAULT_URL}")


def test_the_qr_is_all_shape_and_no_size(client):
    """A booth TV scales it in CSS, and supplies the quiet zone itself — so
    the symbol carries no dimensions and no border of its own."""
    svg = ET.fromstring(client.get("/qr.svg").text)
    modules, _ = segno.make(f"https://{DEFAULT_URL}",
                            error="m").symbol_size(scale=1, border=0)

    assert svg.get("width") is None and svg.get("height") is None
    assert svg.get("viewBox") == f"0 0 {modules} {modules}"


def test_a_configured_url_is_the_one_on_the_wall(make_client):
    client = make_client(submit_url="artwall.example.com")

    assert "artwall.example.com" in client.get("/wall").text
    assert client.get(_qr_url(client)).text == qr_svg("https://artwall.example.com")


def test_an_explicit_scheme_is_left_alone(make_client):
    """The booth-laptop fallback is plain HTTP on an address, not a domain."""
    client = make_client(submit_url="http://192.168.1.5:8000")

    assert client.get("/qr.svg").text == qr_svg("http://192.168.1.5:8000")


def test_the_caption_drops_the_https_a_phone_assumes(make_client):
    client = make_client(submit_url="https://go.example.com/x/")
    html = client.get("/wall").text

    assert "go.example.com/x" in html
    assert "https://go.example.com" not in html


def test_the_caption_keeps_an_http_that_has_to_be_typed(make_client):
    """The runbook sends a moderator to type what the wall shows; without the
    scheme a phone tries HTTPS and the laptop fallback answers nothing."""
    client = make_client(submit_url="http://192.168.1.5:8000")

    assert "http://192.168.1.5:8000" in client.get("/wall").text


def test_the_qr_panel_does_not_cover_the_pieces(client):
    """ADR-0005 keeps "nothing is ever hidden" exactly: the panel sits in
    space the grid reserves for it, and never takes a tile's clicks."""
    css = client.get("/wall").text

    grid = re.search(r"#grid \{(.*?)\}", css, re.S)
    assert grid and "--qr-panel" in grid.group(1), \
        "the grid reserves no room for the QR panel"
    panel = re.search(r"#submit-url \{(.*?)\}", css, re.S)
    assert panel and "pointer-events: none" in panel.group(1)


def test_the_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("ARTWALL_SUBMIT_URL", "go.example.com/other")

    assert Settings.from_env().submit_url == "go.example.com/other"


def test_the_default_needs_no_configuration(monkeypatch):
    monkeypatch.delenv("ARTWALL_SUBMIT_URL", raising=False)

    assert Settings.from_env().submit_url == DEFAULT_URL


def test_an_empty_variable_is_not_a_blank_wall(monkeypatch):
    """Compose passes the variable through whether or not `.env` sets it."""
    monkeypatch.setenv("ARTWALL_SUBMIT_URL", "")

    assert Settings.from_env().submit_url == DEFAULT_URL
