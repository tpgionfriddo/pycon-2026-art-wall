"""Build the post-event static gallery from a running Code Art Wall.

The wall is the event; this is what is left of it afterwards. One command
reads every piece a moderator let through, on any day, out of a deployed
server and writes a directory of plain files: one HTML page, one media file
per piece, nothing else. No server, no build step at the far end, no database
— it is meant to be committed to a repository that GitHub Pages serves, and
to still work in ten years when this stack is long gone.

    python -m artwall.gallery --base-url https://artwall.example.com \\
        --winners 12,45,88

The gallery deliberately lives in a *separate* repository from this one. The
media runs to hundreds of megabytes, Portainer clones this repository on
every redeploy, and the point of that arrangement is shipping a fix from a
phone tether at the booth (see the README). Git objects are forever and
branches do not help: a clone fetches them all.
"""
import argparse
import base64
import getpass
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

TEMPLATES_DIR = Path(__file__).parent / "templates"

DEFAULT_TITLE = "Code Art Wall"
DEFAULT_SUBTITLE = ("Every piece written at the booth, and the Python that "
                    "drew it.")

# Enough of a timeout to pull a 10 MB webm over conference wifi, short enough
# that a wrong --base-url fails while somebody is still watching.
TIMEOUT_S = 120


class GalleryError(Exception):
    """Something the operator can fix, reported without a traceback."""


# ---- reading the event off the server ------------------------------------

def _get(url: str, password: str | None) -> bytes:
    request = urllib.request.Request(url)
    if password is not None:
        # The username is not checked (see `require_admin`), but Basic auth
        # has no shape without one.
        token = base64.b64encode(f"booth:{password}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise GalleryError(
                f"{url} refused the moderator password. This is the same "
                "password as /admin, the one set as ARTWALL_ADMIN_PASSWORD "
                "on the stack.") from exc
        raise GalleryError(f"{url} returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise GalleryError(f"Could not reach {url}: {exc.reason}") from exc


def fetch_pieces(base_url: str, password: str) -> list[dict]:
    """Every approved or archived piece, as the export endpoint gives them."""
    url = f"{base_url.rstrip('/')}/admin/export/gallery.json"
    try:
        payload = json.loads(_get(url, password))
    except json.JSONDecodeError as exc:
        raise GalleryError(
            f"{url} did not return JSON. If the answer was an HTML page, the "
            "server in front of it is probably older than this endpoint — "
            "redeploy it.") from exc
    return payload["pieces"]


def download_media(base_url: str, pieces: list[dict], media_dir: Path,
                   log=print) -> list[dict]:
    """Fetch each piece's media beside the page, dropping any that fails.

    A piece whose file cannot be fetched is left out of the gallery entirely
    rather than written as a tile pointing at nothing. One unreadable render
    out of a hundred should not cost the other ninety-nine.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    kept = []
    for piece in pieces:
        name = piece["media_path"]
        if not name:                       # nothing rendered; nothing to show
            continue
        target = media_dir / Path(name).name
        if not target.exists():            # re-runs skip what they already have
            url = f"{base_url.rstrip('/')}/media/{name}"
            try:
                target.write_bytes(_get(url, None))
            except GalleryError as exc:
                log(f"  ! piece {piece['id']}: {exc}")
                continue
        kept.append(piece | {"media_url": f"media/{target.name}"})
    return kept


# ---- a still for every animated piece ------------------------------------

# Halfway through the loop rather than at its start. A loop that fades up from
# black opens on an empty frame, and a grid of those is a grid of empty boxes.
POSTER_AT = 0.5
# Beside the media and named after it, so `rm media/12.*` takes the piece and
# its still together. Removal from the published gallery is a delete and
# nothing else, and it has to stay that way with two files to delete.
# JPEG rather than WebP: the webp encoder is a build option many ffmpeg
# packages leave out (Homebrew's does), and a still nobody can extract is
# worse than one without an alpha channel. The page's ground is black, which
# is what a transparent corner was being composited onto anyway.
POSTER_SUFFIX = ".poster.jpg"


def _ffmpeg_available() -> bool:
    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            return False
    return True


def _duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def build_posters(pieces: list[dict], media_dir: Path, log=print) -> list[dict]:
    """Give every animated piece a still to show before it plays.

    A `<video>` with no poster paints nothing until it has decoded a frame, so
    without this a page of seventy animated pieces opens as a page of empty
    boxes — and stays that way for the ones a phone declines to load at all.
    The still is what the grid shows; the video is attached on top only while
    the tile is on screen.

    Without ffmpeg there is nothing to extract and the pieces come back
    unchanged, which the page falls back to handling by showing the video
    element directly. Said once, out loud, because the difference is visible.
    """
    animated = [p for p in pieces if p["kind"] == "animated"]
    if not animated:
        return pieces
    if not _ffmpeg_available():
        log("  ! ffmpeg not found: animated pieces will have no still to show"
            " before they play. Install ffmpeg and rebuild for a grid that"
            " fills in immediately.")
        return pieces

    posters, made = {}, 0
    for piece in animated:
        source = media_dir / Path(piece["media_path"]).name
        target = source.with_suffix("")
        target = target.with_name(target.name + POSTER_SUFFIX)
        if not target.exists():
            at = _duration_s(source) * POSTER_AT
            result = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}",
                 "-i", str(source), "-frames:v", "1", "-c:v", "mjpeg",
                 "-q:v", "4", str(target)],
                capture_output=True, text=True, timeout=60)
            if result.returncode != 0 or not target.exists():
                log(f"  ! piece {piece['id']}: no still ({result.stderr.strip()[:80]})")
                continue
            made += 1
        posters[piece["id"]] = f"media/{target.name}"
    if made:
        log(f"  {made} stills extracted")
    return [piece | {"poster_url": posters.get(piece["id"])} for piece in pieces]


# ---- turning them into a page --------------------------------------------

# ---- the winner's trophy -------------------------------------------------

# Drawn as pixels because the page is, one character per pixel: `o` outline,
# `#` cup, `.` nothing. The day number is stamped into the cup at rows 1-5,
# columns 5-7, which is why those fifteen cells are solid cup above.
TROPHY = [
    "..ooooooooo..",
    ".o#########o.",
    "oo#########oo",
    "o#o#######o#o",
    "o#o#######o#o",
    ".oo#######oo.",
    "..o#######o..",
    "...o#####o...",
    "....o###o....",
    ".....o#o.....",
    "....ooooo....",
    "...o#####o...",
    "..ooooooooo..",
]
DIGIT_AT = (5, 1)               # column, row of the number's top-left pixel
DIGITS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
}
INK = {"o": "#6B4A12", "#": "#F2B33D", "d": "#4A2D08"}


def trophy_svg(day: int) -> Markup:
    """A small pixel trophy carrying the day number, as inline SVG.

    Inline so the page stays one file, and drawn as merged horizontal runs
    rather than one rect per pixel, which turns 169 elements into about 30.
    A day past nine gets the trophy without a number: the cup is three pixels
    wide and there is nowhere to put a second digit. Three-day events being
    what they are, this has not come up.
    """
    grid = [list(row) for row in TROPHY]
    if 0 <= day <= 9:
        left, top = DIGIT_AT
        for y, row in enumerate(DIGITS[str(day)]):
            for x, pixel in enumerate(row):
                if pixel == "#":
                    grid[top + y][left + x] = "d"

    parts = []
    for colour_key, colour in INK.items():
        rects = []
        for y, row in enumerate(grid):
            x = 0
            while x < len(row):
                if row[x] != colour_key:
                    x += 1
                    continue
                run = x
                while run < len(row) and row[run] == colour_key:
                    run += 1
                rects.append(f'<rect x="{x}" y="{y}" width="{run - x}"'
                             ' height="1"/>')
                x = run
        if rects:
            parts.append(f'<g fill="{colour}">{"".join(rects)}</g>')
    size = len(TROPHY)
    return Markup(f'<svg viewBox="0 0 {size} {size}" aria-hidden="true"'
                  f' focusable="false">{"".join(parts)}</svg>')


def _highlighter():
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import PythonLexer
    except ImportError as exc:            # pragma: no cover - environment
        raise GalleryError(
            "The gallery needs Pygments to colour the source at build time, "
            "so the published page needs no JavaScript of its own. Install "
            "it with:  uv sync --group gallery") from exc
    # A dark style, because the page is dark: a light one would put a white
    # card in the middle of the wall's black.
    formatter = HtmlFormatter(style="dracula", cssclass="hl")
    # The style ships its own ground too, a shade off the page's own.
    css = formatter.get_style_defs(".hl") + "\n  .hl { background: none; }"
    return (lambda code: Markup(highlight(code, PythonLexer(), formatter)),
            Markup(css))


def winner_days(pieces: list[dict], winner_ids: list[int]) -> dict[int, int]:
    """Which piece won which day, from the ids given on the command line.

    Order is the operator's: `--winners 12,45,88` is day one, day two, day
    three. Nothing in the database records the judges' decision, so this flag
    is the only place it exists.
    """
    known = {piece["id"] for piece in pieces}
    missing = [i for i in winner_ids if i not in known]
    if missing:
        raise GalleryError(
            f"--winners names {', '.join(str(i) for i in missing)}, which "
            "no approved or archived piece has. A piece taken down or "
            "rejected is not in the export at all.")
    return {piece_id: day for day, piece_id in enumerate(winner_ids, start=1)}


def render_page(pieces: list[dict], winner_ids: list[int], title: str,
                subtitle: str) -> str:
    """The whole gallery as one HTML document.

    A winner is not lifted out into a band of its own: it keeps its place in
    the grid and wears a trophy in the corner, the way it sat on the wall
    among everything else.
    """
    highlight, pygments_css = _highlighter()
    days = winner_days(pieces, winner_ids)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)),
                      autoescape=select_autoescape(["html"]))
    prepared = [
        piece | {"code_html": highlight(piece["code"]),
                 "day": days.get(piece["id"]),
                 "trophy": trophy_svg(days[piece["id"]])
                           if piece["id"] in days else None}
        for piece in pieces
    ]
    return env.get_template("gallery.html").render(
        pieces=prepared, title=title, subtitle=subtitle,
        pygments_css=pygments_css)


def build(base_url: str, password: str, out_dir: Path, winner_ids: list[int],
          exclude: set[int], title: str, subtitle: str, log=print) -> int:
    """Write the whole gallery into `out_dir`. Returns the piece count."""
    log(f"Reading {base_url} ...")
    pieces = fetch_pieces(base_url, password)
    log(f"  {len(pieces)} approved or archived pieces")
    if exclude:
        pieces = [p for p in pieces if p["id"] not in exclude]
        log(f"  {len(exclude)} excluded by flag")
    if not pieces:
        raise GalleryError("Nothing to publish: the export was empty.")
    # Checked before a single byte of media is fetched. A mistyped winner id
    # is the likeliest thing to be wrong on the command line, and finding out
    # after downloading a few hundred megabytes is a poor way to hear it.
    winner_days(pieces, winner_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    pieces = download_media(base_url, pieces, out_dir / "media", log=log)
    if not pieces:
        raise GalleryError("Nothing to publish: no media could be fetched.")

    pieces = build_posters(pieces, out_dir / "media", log=log)

    (out_dir / "index.html").write_text(
        render_page(pieces, winner_ids, title, subtitle), encoding="utf-8")
    # Pages runs Jekyll over a site without this, which costs a build on every
    # push and would swallow any file whose name begins with an underscore.
    (out_dir / ".nojekyll").write_text("")
    log(f"Wrote {out_dir}/ ({len(pieces)} pieces)")
    return len(pieces)


# ---- the command ---------------------------------------------------------

def _ids(raw: str) -> list[int]:
    return [int(part) for part in raw.replace(",", " ").split()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m artwall.gallery",
        description=__doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True,
                        help="the deployed wall, e.g. https://artwall.example.com")
    parser.add_argument("--out", type=Path, default=Path("site"),
                        help="directory to write (default: site)")
    parser.add_argument("--winners", type=_ids, default=[], metavar="IDS",
                        help="piece ids of the daily winners, in day order,"
                             " e.g. --winners 12,45,88")
    parser.add_argument("--exclude", type=_ids, default=[], metavar="IDS",
                        help="piece ids to leave out of every rebuild")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--subtitle", default=DEFAULT_SUBTITLE)
    parser.add_argument("--password", default=None,
                        help="the moderator password. Read from"
                             " ARTWALL_ADMIN_PASSWORD, or prompted for, when"
                             " not given — a password on the command line"
                             " ends up in the shell history.")
    args = parser.parse_args(argv)

    password = (args.password or os.environ.get("ARTWALL_ADMIN_PASSWORD")
                or getpass.getpass("Moderator password: "))
    try:
        build(args.base_url, password, args.out, args.winners,
              set(args.exclude), args.title, args.subtitle)
    except GalleryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
