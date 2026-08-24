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
