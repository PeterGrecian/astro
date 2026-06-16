"""Per-camera configuration loader.

Each camera has a directory <repo>/<name>/ containing camera.json
(hardware + pipeline facts) plus optional sibling files with their own
lifecycles: occlusion.json, quality.json, location.json, privacy.json.

Usage:
    from astro.config import CameraConfig
    cam = CameraConfig.load("astrocam")
    cam.bayer, cam.frames_root, cam.s3["bucket"]
    cam.occlusion          # dict or None
"""
import json
import os
from pathlib import Path

# ASTRO_REPO_ROOT overrides where camera dirs are looked up (tests).
REPO_ROOT = Path(os.environ.get("ASTRO_REPO_ROOT",
                                Path(__file__).resolve().parent.parent))

_SIBLINGS = ("occlusion", "quality", "location", "privacy")


class CameraConfig:
    def __init__(self, data: dict, camera_dir: Path):
        self._data = data
        self.camera_dir = camera_dir
        for key in _SIBLINGS:
            fname = data.get(f"{key}_file")
            val = None
            if fname and (camera_dir / fname).exists():
                val = json.loads((camera_dir / fname).read_text())
            setattr(self, key, val)

    @classmethod
    def load(cls, name: str, repo_root: Path | None = None) -> "CameraConfig":
        camera_dir = (repo_root or REPO_ROOT) / name
        cfg_path = camera_dir / "camera.json"
        if not cfg_path.exists():
            raise FileNotFoundError(f"no camera.json for '{name}' at {cfg_path}")
        return cls(json.loads(cfg_path.read_text()), camera_dir)

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(f"{self._data.get('name', '?')}: no config field '{key}'")

    def get(self, key, default=None):
        return self._data.get(key, default)

    @property
    def frames_root(self) -> Path:
        return Path(self._data["frames_root"]).expanduser()

    @property
    def stack_brightness_max_per_s(self):
        """Quality threshold on mean/(EXPTIME*GAIN) above which a frame is
        twilight/moonlight-polluted and must not enter stacks. Comes from
        the sibling quality.json when its camera matches this sensor
        (eclipticam's file covers only the v3w/imx708; v1 is unset)."""
        q = self.quality
        sensor = self._data.get("sensor") or ""
        if q and q.get("camera", "").lower() == sensor.lower():
            return q.get("stack_brightness_max_per_s")
        return None

