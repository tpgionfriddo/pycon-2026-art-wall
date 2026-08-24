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
    rate_limit_max: int = 5
    rate_limit_window_s: int = 600
    max_queue_depth: int = 100
    worker_image: str = "artwall-worker"
    render_timeout_s: int = 60
    poll_interval_s: float = 2.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "artwall.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("ARTWALL_DATA_DIR", "data")),
            admin_password=os.environ.get("ARTWALL_ADMIN_PASSWORD", ""),
            worker_image=os.environ.get("ARTWALL_WORKER_IMAGE", "artwall-worker"),
        )
