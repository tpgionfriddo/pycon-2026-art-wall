# All pages use a JetBrains-branded light theme

All five pages (wall, submit, piece, status, admin) share a light theme
branded for the JetBrains booth: white / near-white surfaces, near-black
text, and the JetBrains logo gradient — #FC801D → #FF318C → #6B57FF, from
the official palette at jetbrains.com/company/brand — as the accent for
headings, buttons, and toasts, with JetBrains purple #6B57FF as the single
interactive color. Headings and code are set in JetBrains Mono, loaded from
Google Fonts (every page already requires internet, ADR-0001/ADR-0004).
Branding stays at "gradient accents" only: embedding the JetBrains logo was
rejected to avoid shipping and maintaining logo assets under the brand
guidelines.

## Consequences

- Pieces are often dark-background art; on the light wall they read as
  framed dark artwork — the intended gallery look.
- One more CDN dependency (Google Fonts) on every page, including admin;
  the font stacks must fall back to system fonts if the CDN is unreachable.
- The dark palette is fully removed (`color-scheme: light` everywhere);
  there is no theme toggle.

## Amendment (2026-08-24): the wall is dark, the other four pages stay light

The wall is a gallery surface, not a working surface. Against a light
background the tiles read as a grid of documents; against near-black the
chrome recedes and the pieces themselves carry the screen — which is the
whole point of the booth TV. So the wall alone uses a dark ground, while
submit, status, piece, admin — and the terms page added after this
amendment — keep the light theme described above.
The logo-gradient accent and JetBrains Mono are unchanged on every page.

This also reverses this ADR's rejection of shipping logo assets: the wall
carries the PyCharm logo, so the asset is committed and served from a
dedicated static mount (`artwall/static/`) rather than from the rendered-media
directory, which is runtime state and is not in version control.
