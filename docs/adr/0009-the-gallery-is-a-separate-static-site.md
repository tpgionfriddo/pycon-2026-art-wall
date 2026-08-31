# The post-event gallery is a separate static site

`python -m artwall.gallery` reads a deployed wall over HTTP and writes a
directory of plain files — one `index.html`, one media file per piece — meant
to be committed to **its own repository** and served by GitHub Pages. Chosen
over serving the gallery from this application (which would keep the VPS, the
worker image and the database alive for a page nobody edits), and over
publishing it from this repository.

The separate repository is the load-bearing part. The media runs to hundreds
of megabytes, Portainer clones this repository on every redeploy, and the
whole point of that arrangement (ADR-0007) is shipping a fix from a phone
tether at the booth. Git objects are permanent and a branch does not help: a
clone fetches them all.

## Consequences

- The gallery is built from `/admin/export/gallery.json`, which carries the
  byline, kind, media path and code and none of the contact info. A public
  website is generated verbatim from that payload, so the omission is made at
  the server rather than trusted to the generator.
- It publishes `approved` *and* `archived` pieces. Archived is how a day ends
  (ADR: `db.archive`), so an export of `approved` alone would silently
  publish the last day of the event and call it the gallery. `removed` — a
  takedown — stays out, as it stays off the wall.
- Pieces are pulled from the published gallery by deleting the media from
  that repository. A tile whose image 404s hides itself, so `rm media/14.*`
  is the whole operation — the glob because an animated piece is two files
  sharing a stem. A rebuild fetches it again; `--exclude` is what makes a
  removal survive one.
- The grid is **stills**, not videos. A `<video>` paints nothing until it has
  decoded a frame, so seventy of them open as seventy empty boxes, and a
  phone declines to load that many media players at all. ffmpeg extracts one
  frame per animated piece at build time (mid-loop, since a loop that fades
  up from black opens on nothing), and the page attaches a video to a tile
  only while it is on screen. What is on screen is the bound and it counts
  itself: about ten pieces on a phone and fifty on a desktop, all moving. The
  wall plays every approved piece at once on the booth TV and was tested at
  fifty tiles (ADR-0003), so a screenful of loops is not the thing to be
  careful about; holding a media player for all seventy seven is. Tiles are
  200px rather than 160px for the same reason: the smaller tile fitted a
  whole 1080p screenful of pieces, more than a browser hands out players for,
  so a third of the grid sat still. Above a screenful that large some tiles
  stay still whatever the ceiling says, and the ones nearest the middle of
  the screen win. Without ffmpeg the build carries on and falls back to bare
  video elements, loudly.
- The highlighted source is inlined in `<template>` elements rather than
  hidden divs. Seventy pieces of syntax-highlighted Python is a span per
  token: 158,658 live DOM nodes as divs against 499 as templates, all of the
  difference being nodes laid out for a panel nobody had opened.
- The page is dark, like the wall and unlike the four light pages ADR-0006
  describes. It is the wall after the event, and the pieces were composed
  against black.
- The source is highlighted at build time (Pygments) and inlined, about 2 KB
  per piece compressed, so the published page fetches nothing but its own
  media and keeps working with no CDN behind it.
- Pygments is a `gallery` dependency group, not a runtime dependency: the
  generator runs on a laptop and the application image has no use for it.
