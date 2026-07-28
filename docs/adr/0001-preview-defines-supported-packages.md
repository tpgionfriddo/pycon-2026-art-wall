# Mandatory browser preview defines the supported package set; py5 is dropped

Attendees must render their piece in a client-side Pyodide preview before they
can submit — code that cannot run in the preview cannot be submitted at all.
Consequently, the contest supports exactly one fixed set of packages: those
that work both in Pyodide (built-in or via micropip) and in the Docker render
worker. py5 (JVM-based, cannot run in Pyodide) is dropped entirely, including
the "advanced booth-laptop" path described in the original brief.

## Considered options

- **Preview as optional enhancement / escape hatch for worker-only libraries**
  — rejected for simplicity: one supported package list, one contract,
  everything on the wall was browser-verified before it ever hit the queue.
- **Keep py5 as a separate booth-only format** — rejected; it would need a
  second render pipeline (offscreen frame capture) for a single format that
  attendees at home could never use.

## Consequences

- The Docker worker image and the preview must install the same package list;
  drift between them silently breaks the "preview succeeded ⇒ worker will
  succeed" promise (modulo sandbox limits like timeout/memory).
- `samples/py5_orbits.py` is no longer a supported submission format.
- The preview is a hard dependency of the submission page: no Pyodide, no
  submissions from that browser.
