# The system is hosted on a cloud VPS with a public URL

Server, worker, and Docker all run on a small cloud VPS behind a real domain;
the booth QR code points at the public URL and the wall TV is just a browser
on that same URL. Chosen over hosting on the booth laptop because conference
Wi-Fi commonly enforces AP/client isolation (attendee devices cannot reach a
laptop on the same network), attendees can fall back to mobile data, and the
mandatory Pyodide preview already requires internet anyway.

## Consequences

- The submission endpoint is reachable from the whole internet, so basic
  abuse guards (rate limiting, code-size caps) are required — moderation
  alone only protects the wall, not the render queue.
- Fallback if venue internet dies at the TV: the identical stack runs on the
  booth laptop (Docker + two `uv run` processes); the code must not assume
  anything VPS-specific.

## Amendment (2026-08-24): how it is actually deployed

This record decides the VPS and says nothing about the shape of the
deployment. The reverse proxy that terminates TLS, the certificates it obtains
itself, and the Portainer git stack the whole thing is deployed as are decided
in ADR-0007, which also carries the abuse-guard consequence above forward: the
submission rate limit only counts attendees rather than the proxy because the
proxy rewrites `X-Forwarded-For` and the server trusts it.

## Amendment (2026-08-25): a short link in front of the public URL

The decision above has the booth QR point at the public URL. It now points at
a **Submit URL** — a short link on a domain the booth owns, redirected there —
and the wall itself carries that QR with the address printed under it, rather
than paper alone. Two reasons: the link is short enough to read off a TV and
type by hand, and moving the stack (a new domain, the laptop fallback) is then
a redirect rather than a reprint of everything already handed out.

The cost is a second thing that can be wrong, and one this repo cannot fix:
the redirect lives wherever that domain is administered. The runbook carries
the symptom ("The QR on the wall goes nowhere") and says as much.

`ARTWALL_SUBMIT_URL` configures it, and its default in `artwall/config.py` is
this event's link — the one event-specific value in the code, and a knowing
exception to "the code must not assume anything VPS-specific" above, which is
about the *stack's* address rather than the poster's. A value with no scheme
is scanned as `https://`; the laptop fallback sets an explicit `http://`, and
the wall then shows the scheme too, because it has to be typed.
