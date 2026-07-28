# Code Art Wall

A conference-booth activity: attendees write Python code that generates art,
submit it with contact info, and approved pieces appear on a big-screen wall.

## Language

**Piece**:
One rendered artwork on the wall — the output media (static image or looping
video) plus its author attribution.
_Avoid_: artwork, image, entry

**Submission**:
The Python source code plus the attendee's contact info and consent, as
received by the server. A submission becomes a piece once rendered and
approved.
_Avoid_: upload, entry

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

**Moderation**:
The mandatory human review of a rendered submission before it may appear on
the wall. A submission is either approved or rejected; nothing is displayed
unreviewed.
_Avoid_: review, curation, vetting

**Supported Packages**:
The single fixed list of Python packages available to submissions — exactly
those that work both in the preview (Pyodide/micropip) and in the render
worker. py5 is explicitly not supported.
_Avoid_: allowed libraries, whitelist

**Draw Contract**:
The rule that submission code defines exactly one of `draw()` (static) or
`draw(t)` (animated, `t` sweeping 0→1 over one perfect loop).
_Avoid_: API, interface
