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

# The Submit URL the wall invites attendees to: a short link on a domain the
# booth owns, redirected at the public URL (ADR-0004's second amendment).
# This default is the one event-specific address in the code, which is why
# every deployment can override it — see `from_env` below.
SUBMIT_URL = "go.adeptask.com/pycon26"


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
    # The base the render worker builds each job's scratch under. Unset means
    # the system temporary directory; see `artwall.worker.check_scratch_base`
    # for why a containerised worker has to be told somewhere else.
    scratch_dir: Path | None = None
    # The Submit URL as configured: scheme optional, and not this stack's own
    # address. See `CONTEXT.md`.
    submit_url: str = SUBMIT_URL

    @property
    def db_path(self) -> Path:
        return self.data_dir / "artwall.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def qr_target(self) -> str:
        """What the wall's QR encodes: an absolute URL. A configured value
        without a scheme is scanned as `https://` — the booth-laptop fallback
        runs on plain HTTP and has to say so."""
        if "://" in self.submit_url:
            return self.submit_url
        return f"https://{self.submit_url}"

    @property
    def submit_url_shown(self) -> str:
        """What a reader types off the wall. Drops `https://`, which a phone
        assumes, and nothing else: an explicit `http://` is the booth-laptop
        fallback, and typing the address without it reaches nothing."""
        shown = self.submit_url
        if shown.startswith("https://"):
            shown = shown[len("https://"):]
        return shown.rstrip("/")

    @classmethod
    def from_env(cls) -> "Settings":
        scratch = os.environ.get("ARTWALL_SCRATCH_DIR", "")
        return cls(
            data_dir=Path(os.environ.get("ARTWALL_DATA_DIR", "data")),
            admin_password=os.environ.get("ARTWALL_ADMIN_PASSWORD", ""),
            worker_image=os.environ.get("ARTWALL_WORKER_IMAGE", "artwall-worker"),
            scratch_dir=Path(scratch) if scratch else None,
            # Empty means unset: Compose passes the variable through whether
            # or not `.env` gives it a value, and a blank wall QR is worse
            # than the wrong one.
            submit_url=os.environ.get("ARTWALL_SUBMIT_URL", "") or SUBMIT_URL,
        )
