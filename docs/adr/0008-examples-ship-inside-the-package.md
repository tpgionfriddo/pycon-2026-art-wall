# Examples ship inside the package, not in `samples/`

The submission page offers a dropdown of working code an attendee can load
into the editor. Those Examples live in `artwall/examples/`, inside the
application package, and the three curated ones were **moved** out of
`samples/` rather than copied.

## Why not `samples/`, where the art already was

`.dockerignore` excludes `samples/*` apart from the render harness, and
`Dockerfile` copies only `artwall`. So nothing under `samples/` exists in
either service image: an Example served from there would be a broken
dropdown entry in production and would work only on the developer's laptop.
Putting them in the package means `COPY artwall` already covers them and
neither file needed changing.

Moving rather than copying is the other half of the decision. Two homes for
the same art is two files to keep in step, and the copy nobody renders is
the one that rots.

## Why the renders stay behind

The `.gif` renders of the moved pieces stay in `samples/`. Two of them are
10.2 MB and 4.4 MB, and the package is copied wholesale into both the
application and the worker image, so moving them next to their code would
ship roughly 15 MB of GIF twice over. Nothing but a human browsing the
repository reads them, and that human is reading GitHub, not a container.

The cost is that a moved file's name no longer pairs with the render left
behind, because Examples are numbered to make the dropdown's order visible
on disk. `samples/README.md` carries the mapping.

## Consequences

- `tests/test_pipeline.py` covers `samples/` only. It is skipped without
  Docker and the sandbox image, so at the booth it protects nothing; the
  Examples are guarded by `tests/test_examples.py`, which always runs.
- Examples are attendee-facing code in a directory of otherwise internal
  Python. `CONTEXT.md` defines Example, Sample and Scaffold to keep that
  boundary legible.
- Adding an Example means adding a tuple to `EXAMPLES` in
  `artwall/config.py`. A file added without one is invisible on the page,
  which is why `tests/test_examples.py` refuses to let the directory and the
  list disagree.
