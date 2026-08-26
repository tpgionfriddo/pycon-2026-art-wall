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

## Amendment (2026-08-25): the logo gradient is retired as an accent

This supersedes the 2026-08-24 amendment's closing claim that "the
logo-gradient accent and JetBrains Mono are unchanged on every page". The
gradient half of that is no longer true, and deliberately so.

The submit page is the first thing an attendee sees, and the gradient made it
read as decorated rather than written: a three-color rule under the header and
a heading whose text was filled with the gradient instead of colored. Removing
it there (issue 15) left that page the only plain one, so the treatment is now
removed from the other four light pages too. Headings on submit, status, piece,
terms and admin are near-black `#19191c`, and the header rule is a plain
`1px solid #d8d8e0` matching the other rules already on those pages.

The gradient is therefore no longer used anywhere in the stack. The wall's
branding does not depend on it: the wall carries the actual PyCharm logo asset
(previous amendment), which is stronger branding than a gradient quoting one.

The page roster is now six, not the five this ADR's opening line counts: the
terms page arrived after that line was written. Five of the six are light
(submit, status, piece, terms, admin) and the wall is dark.

Unchanged, and still the substance of this ADR:

- JetBrains Mono for headings and code, on every page.
- JetBrains purple `#6B57FF` as the single interactive color.
- Light surfaces on the five light pages; the dark ground on the wall.
- No logo embedding beyond the committed wall asset.

Consequence: "gradient accents" is no longer the branding mechanism. The
branding is the typeface, the single interactive color, and the wall's logo.
A future page should not reintroduce the gradient to look consistent with the
others, because none of them carry it.
