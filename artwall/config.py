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
    render_timeout_s: int = 60
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
        )
