# Wall tiles are uniform and always fill the screen

The wall lays out all approved pieces as identical square tiles whose size is
computed client-side from the piece count and the viewport: for N pieces it
picks the column count that maximises tile size, so a handful of pieces fills
the whole screen (one piece ≈ fullscreen, four ≈ quarters) and tiles shrink —
without limit and without scrolling — as the wall grows. Chosen over
mixed-size mosaics, collages, and featured/big tiles (all considered and
rejected: every piece stays equal) and over the previous fixed stepwise
minimum sizes, which left a nearly empty wall looking sparse at the booth.

## Consequences

- Static pieces are capped at 1024×1024 and animated ones at 512×512 (MVP
  plan §3), so near-fullscreen tiles are upscaled in the browser; the
  resulting softness is explicitly accepted.
- "Nothing is ever hidden" is kept exactly: the page never scrolls; with
  hundreds of pieces the tiles become very small.
- Tile size changes animate (~0.5 s CSS transition) when a piece lands or
  the window resizes, so the booth TV reflows gracefully.

## Amendment (2026-08-25): the QR gets a column, not an overlay

The wall's QR and Submit URL sit in the bottom-left corner, and the grid
*reserves* that width rather than letting tiles run under it. An overlay was
the obvious way and is rejected here: it would hide the corner of a
near-fullscreen piece, cover whole tiles once they are small, and swallow the
clicks that open a piece — all of which "nothing is ever hidden" above rules
out. (The toast overlays tiles, but it is transient and passes clicks
through.)

The reservation is usually free: tile size is `min(width-fit, height-fit)`,
and on a 16:9 screen the height is what binds, so a column off the width
changes nothing for the pieces. `layout()` therefore reads the grid's real
padding instead of assuming it — the panel's size is set in CSS, in one
custom property the padding is derived from.
