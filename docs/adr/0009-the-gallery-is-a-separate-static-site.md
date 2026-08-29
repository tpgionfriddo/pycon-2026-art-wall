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
- Pieces are pulled from the published gallery by deleting the media file
  from that repository. A tile whose media 404s hides itself, so a plain `rm`
  is the whole operation. A rebuild fetches it again; `--exclude` is what
  makes a removal survive one.
- The page is dark, like the wall and unlike the four light pages ADR-0006
  describes. It is the wall after the event, and the pieces were composed
  against black.
- The source is highlighted at build time (Pygments) and inlined, about 2 KB
  per piece compressed, so the published page fetches nothing but its own
  media and keeps working with no CDN behind it.
- Pygments is a `gallery` dependency group, not a runtime dependency: the
  generator runs on a laptop and the application image has no use for it.
