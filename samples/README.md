# Samples

Internal art and test fixtures. Nothing here is attendee-facing: the pieces
in this directory are what `tests/test_pipeline.py` renders end to end
through the sandbox image, plus `preview.py`, the harness that renders one
file to a PNG or a looping GIF:

```bash
uv run python samples/preview.py samples/plasma_shader.py
```

`py5_orbits.py` is deliberately not contract-compliant. py5 is not a
Supported Package, and the file exists so that stays visible.

## Three pieces moved to `artwall/examples/`

They are loadable from the submission page's "Load an example" dropdown now,
so they live inside the package: the application image copies `artwall`
wholesale and excludes this directory entirely. They were renumbered on the
way, so the names no longer pair up with the renders left behind here:

| Was | Is now |
|---|---|
| `adeptask_logo_ish.py` | `artwall/examples/04_unfolding_spectrum.py` |
| `torus_wireframe.py` | `artwall/examples/05_spinning_torus.py` |
| `aquion_logo.py` | `artwall/examples/06_aquion_logo.py` |

Their `.gif` renders stayed here on purpose. Two of them are 10.2 MB and
4.4 MB, and moving them next to their code would ship roughly 15 MB of GIF
inside both service images. See `docs/adr/0008-examples-ship-inside-the-package.md`.
