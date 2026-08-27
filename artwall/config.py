"""Runtime settings, overridable through environment variables.

Nothing here may assume VPS specifics (ADR-0004): the identical stack must
run on the booth laptop.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

# The single fixed list of Supported Packages (ADR-0001): identical in the
# Pyodide preview and in the render worker image.
SUPPORTED_PACKAGES = [
    "numpy", "matplotlib", "Pillow", "pandas", "shapely", "scipy",
    "colour", "trimesh", "svgpathtools",
]

# The submission page's "Load an example" dropdown, in the order it shows
# them, grouped by the headings below. The list is explicit rather than
# derived from the directory for three reasons: attendee-facing labels stay
# reviewable in one place, the order is literal rather than alphabetical, and
# the files' own docstrings are internal notes written in a register this page
# does not use. A file added here without a tuple is invisible on the page,
# which is what `tests/test_examples.py` exists to catch.
EXAMPLES_DIR = Path(__file__).parent / "examples"
EXAMPLES = [
    # Start here
    ("00_scaffold.py", "Your piece"),
    # Learn
    ("01_still_image.py", "A still image"),
    ("02_a_plot_as_art.py", "A plot as art"),
    ("03_text_and_shapes.py", "Text and shapes"),
    # Finished pieces
    ("04_unfolding_spectrum.py", "Unfolding spectrum"),
    ("05_spinning_torus.py", "Spinning torus"),
    ("06_aquion_logo.py", "Aquion logo afloat"),
]
# Which of the above sit under each dropdown heading, in order. Named rather
# than counted: counts that happen to add up can still group the wrong files,
# and nothing would say so. The page renders these groups rather than the flat
# list, so an example missing from here is invisible even with a tuple above.
EXAMPLE_GROUPS = [
    ("Start here", ["00_scaffold.py"]),
    ("Learn", ["01_still_image.py",
               "02_a_plot_as_art.py",
               "03_text_and_shapes.py"]),
    ("Finished pieces", ["04_unfolding_spectrum.py",
                         "05_spinning_torus.py",
                         "06_aquion_logo.py"]),
]

FRAMES, FPS = 150, 30          # 5 s perfect loop
VIDEO_BOX = 512                # animated pieces fit in 512×512
STATIC_BOX = 1024              # static pieces downscaled to fit 1024×1024

# The only media filenames the harness may produce, per kind — keep identical
# to what worker/render_job.py writes. The worker moves a file by the name the
# harness hands back, so a submission does not get to choose it.
MEDIA_NAMES = {"static": "piece.png", "animated": "piece.webm"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path("data"))
    admin_password: str = ""
    max_code_bytes: int = 32 * 1024
    # Per client address, and at a conference an address is not a person:
    # venue wifi puts the whole hall behind one NAT. So the ceiling has to
    # clear a hall, not a person. One attendee can still consume the whole
    # hall's allowance, which is accepted — what stands between a flood and
    # the booth is max_queue_depth below, and no piece reaches the wall
    # without a moderator. What this uniquely protects is the render worker's
    # time, and the worker drains faster than the moderator does.
    rate_limit_max: int = 60
    rate_limit_window_s: int = 600
    max_queue_depth: int = 100
    worker_image: str = "artwall-worker"
    # The slowest shipped Example renders in about 15 s on one dedicated
    # CPU, and halving a container's CPU was measured to cost about 3.3x
    # rather than 2x, so a starved host puts that piece near 50 s and the old
    # 60 s ceiling killed work that was fine. This still has to bound a
    # submission that never finishes: it is the only thing that does. Neither
    # --memory, --pids-limit nor --cpus stops `while True: pass`, the worker
    # renders one job at a time, and `requeue_stale_rendering` hands a
    # `rendering` row straight back on restart, so an unbounded job stops the
    # wall for the rest of the event and survives a worker restart.
    render_timeout_s: int = 180
    # How many CPUs one render may use. Animated pieces draw in Python while
    # ffmpeg encodes, two processes through a pipe, so a one-CPU cap
    # serialises work that could overlap: measured on the slowest Example,
    # 15.1 s at one CPU against 7.1 s at two, and 6.0 s at three. Two takes
    # nearly all of it. The worker renders one job at a time, so this is the
    # most rendering can ever take from the host, whatever the queue depth.
    render_cpus: float = 2.0
    poll_interval_s: float = 2.0
    # The base the render worker builds each job's scratch under. Unset means
    # the system temporary directory; see `artwall.worker.check_scratch_base`
    # for why a containerised worker has to be told somewhere else.
    scratch_dir: Path | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "artwall.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @classmethod
    def from_env(cls) -> "Settings":
        scratch = os.environ.get("ARTWALL_SCRATCH_DIR", "")
        defaults = cls()
        return cls(
            data_dir=Path(os.environ.get("ARTWALL_DATA_DIR", "data")),
            admin_password=os.environ.get("ARTWALL_ADMIN_PASSWORD", ""),
            worker_image=os.environ.get("ARTWALL_WORKER_IMAGE", "artwall-worker"),
            scratch_dir=Path(scratch) if scratch else None,
            # Tunable so a jammed booth is answered with a stack variable
            # rather than a commit and a redeploy.
            rate_limit_max=int(os.environ.get(
                "ARTWALL_RATE_LIMIT_MAX", defaults.rate_limit_max)),
            rate_limit_window_s=int(os.environ.get(
                "ARTWALL_RATE_LIMIT_WINDOW_S", defaults.rate_limit_window_s)),
            # The render ceiling belongs here for the same reason: a booth
            # killing renders it should not be needs an answer faster than a
            # redeploy. It was the one dial left out, and that is how it was
            # found. `tests/test_settings_from_env.py` now fails if any
            # field on this class is unreachable from the environment.
            render_timeout_s=int(os.environ.get(
                "ARTWALL_RENDER_TIMEOUT_S", defaults.render_timeout_s)),
            render_cpus=float(os.environ.get(
                "ARTWALL_RENDER_CPUS", defaults.render_cpus)),
            max_queue_depth=int(os.environ.get(
                "ARTWALL_MAX_QUEUE_DEPTH", defaults.max_queue_depth)),
            max_code_bytes=int(os.environ.get(
                "ARTWALL_MAX_CODE_BYTES", defaults.max_code_bytes)),
            poll_interval_s=float(os.environ.get(
                "ARTWALL_POLL_INTERVAL_S", defaults.poll_interval_s)),
        )
