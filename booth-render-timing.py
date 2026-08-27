#!/usr/bin/env python3
"""Time the seven shipped Examples through the real sandbox, on this host.

Run this ON THE BOX that is failing renders:

    python3 booth-render-timing.py                # needs the artwall repo alongside
    ARTWALL_WORKER_IMAGE=artwall-worker python3 booth-render-timing.py

Prints one line per Example with wall-clock elapsed and whether it would be
killed by the 60 s ceiling. Nothing is written to the database and no
submission is touched: each render goes to a throwaway directory.

Compare the numbers against the reference measured on a dev laptop
(1 dedicated CPU per container, macOS, Docker Desktop):

    00_scaffold            2.7s
    01_still_image         0.6s
    02_a_plot_as_art       0.5s
    03_text_and_shapes     0.6s
    04_unfolding_spectrum 13.3s
    05_spinning_torus     15.0s   <- worst
    06_aquion_logo         6.5s

If this host is several times slower than that, the ceiling is the symptom
and the host's CPU share is the cause: raising ARTWALL_RENDER_TIMEOUT_S stops
good pieces being thrown away but does not make them arrive any sooner. Halving a container's CPU was measured
to cost about 3.3x, not 2x, so a small margin here is not a small margin.
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    # Stdlib-only module, so this works under plain python3 with no venv.
    from artwall.config import Settings as _Settings
    _default_ceiling = _Settings().render_timeout_s
except Exception:                                   # run from somewhere else
    _default_ceiling = 180

IMAGE = os.environ.get("ARTWALL_WORKER_IMAGE", "artwall-worker")
CEILING = int(os.environ.get("ARTWALL_RENDER_TIMEOUT_S", _default_ceiling))
FLAGS = ["--network", "none", "--memory", "1g", "--cpus", "1",
         "--pids-limit", "128", "--cap-drop", "ALL",
         "--security-opt", "no-new-privileges"]

here = Path(__file__).resolve().parent
examples = next((p for p in (here / "artwall" / "examples",
                             here.parent / "artwall" / "examples")
                 if p.is_dir()), None)
if examples is None:
    sys.exit("cannot find artwall/examples next to this script")

print(f"image={IMAGE}  ceiling={CEILING}s  host cpus={os.cpu_count()}\n")
worst = (0.0, "")
for src in sorted(examples.glob("*.py")):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "s.py").write_text(src.read_text())
        (td / "out").mkdir()
        t0 = time.monotonic()
        subprocess.run(
            ["docker", "run", "--rm", *FLAGS,
             "-v", f"{td / 's.py'}:/job/submission.py:ro",
             "-v", f"{td / 'out'}:/out", IMAGE,
             "python", "/app/render_job.py", "/job/submission.py", "/out"],
            capture_output=True, timeout=CEILING * 10)
        elapsed = time.monotonic() - t0
        result_file = td / "out" / "result.json"
        result = json.loads(result_file.read_text()) if result_file.exists() else {}
        media = bool(result.get("media")) and (td / "out" / result["media"]).exists()
    verdict = "WOULD BE KILLED" if elapsed > CEILING else "ok"
    print(f"  {elapsed:7.1f}s  {verdict:15}  {'' if media else 'NO MEDIA  '}"
          f"{src.stem}")
    worst = max(worst, (elapsed, src.stem))

print(f"\nworst: {worst[1]} at {worst[0]:.1f}s "
      f"({worst[0] / CEILING:.0%} of the {CEILING}s ceiling)")
