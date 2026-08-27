# Code Art Wall

A conference-booth activity: attendees write Python code that generates art,
submit it with contact info, and approved pieces appear on a big-screen wall.

## Language

**Piece**:
One rendered artwork on the wall — the output media (static image or looping
video) plus its byline, where the attendee kept one.
_Avoid_: artwork, image, entry

**Byline**:
The public credit shown with a piece on the wall — a name or handle the
attendee chooses. Normally the name they gave, but they may substitute
anything or clear it entirely; a cleared byline means the piece is displayed
unattributed. Never their email.
Byline is the term in code, in the database, and on the wire: the form field is
`byline`. The submit form labels it **Displayed name** for attendees, who do
not share our vocabulary; that label is the one exception, not a rename.
_Avoid_: display name, username, attribution

**Submission**:
The Python source code plus the attendee's contact info and consent, as
received by the server. A submission becomes a piece once rendered and
approved.
_Avoid_: upload, entry

**Contact Info**:
What the form collects about the attendee rather than about the piece: first
name, last name, email, and optionally a phone number and a company. First
name and last name together make the **contact name**, which is the whole name
the organisers see on the status page, in `/admin` and in the CSV export. None
of it is ever attendee-facing — that is the byline's job — and none of it
reaches the wall.
_Avoid_: personal details, PII, lead

**Preview**:
The mandatory client-side (Pyodide, in-browser) render of a submission's code.
A successful preview is required before the code can be submitted.
_Avoid_: simulation, dry run

**Render Worker**:
The sandboxed Docker process that executes submission code once and produces
the piece's media file. The only place attendee code ever runs server-side.
_Avoid_: renderer, runner, sandbox (the sandbox is a property of the worker)

**Wall**:
The fullscreen web page on the booth TV showing the grid of approved pieces.
_Avoid_: display, screen, gallery

**Tile**:
One piece's square place on the wall. All tiles are the same size, computed
from the piece count and the viewport so the pieces always fill the screen
(ADR-0005); nothing ever scrolls off.
_Avoid_: cell, thumbnail, slot

**Moderation**:
The mandatory human review of a rendered submission before it may appear on
the wall. A submission is either approved or rejected; nothing is displayed
unreviewed.
_Avoid_: review, curation, vetting

**Takedown**:
The removal of an already-approved piece from the wall. Distinct from a
rejection, which was never displayed to anyone.
_Avoid_: unapprove, delete, hide

**Archive**:
Retiring a piece from the wall because the event has moved on to a new day,
so the next day starts on an empty wall. Neither a takedown nor a judgement:
the moderator's approval stands and is left untouched in the record, the
piece's own page keeps resolving for an attendee who saved the link, and only
the wall changes. Reachable only from an approved piece, one piece at a time,
and like a takedown it cannot be undone from the moderation queue.
_Avoid_: reset, clear, delete, unpublish, rotate

**Supported Packages**:
The single fixed list of Python packages available to submissions — exactly
those that work both in the preview (Pyodide/micropip) and in the render
worker. py5 is explicitly not supported.
_Avoid_: allowed libraries, whitelist

**Draw Contract**:
The rule that submission code defines exactly one of `draw()` (static) or
`draw(t)` (animated, `t` sweeping 0→1 over one perfect loop).
_Avoid_: API, interface

**Example**:
One of the pieces of working code an attendee can load into the editor from
the submission page's "Load an example" dropdown. Examples live in
`artwall/examples/`, are listed in `EXAMPLES` in `artwall/config.py`, and are
attendee-facing: their comments and labels follow the same copy rules as the
page around them. Some teach one corner of the Draw Contract; the rest are
finished pieces.
_Avoid_: sample, demo, template

**Sample**:
Internal art in `samples/`. Test fixtures for the end-to-end render test and
art kept for the repository's own sake. Never attendee-facing, so a sample's
docstring is a note to whoever maintains it. Three former samples became
Examples; the distinction is who reads them, not what they draw.
_Avoid_: example, fixture

**Scaffold**:
The Example the editor opens with. An Example like any other, first in the
dropdown, so re-picking it is how an attendee starts over. It is the one
Example that returns opaque three-channel colour rather than
transparent-cornered RGBA.
_Avoid_: starter, seed, boilerplate, default
