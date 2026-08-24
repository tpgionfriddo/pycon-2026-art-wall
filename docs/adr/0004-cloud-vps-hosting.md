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
