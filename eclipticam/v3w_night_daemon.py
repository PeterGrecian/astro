#!/usr/bin/env python3
"""eclipticam-v3w-night — long-running streaming capture for v3w.

Started by systemd when eclipticam-capture.service flips v3w to
night mode; exits when:
  - SIGTERM (eclipticam-capture flipped back to day) → exit 0
  - frame mean crosses the dawn saturation threshold → exit 0
  - camera error → exit non-zero (systemd Restart=on-failure)

Writes Rice-compressed FITS to /var/lib/eclipticam-buffer/v3w/. The
eclipticam-v3w-uploader.service drains that dir to NFS asynchronously.
"""
import logging
import os
import sys
from pathlib import Path

# Allow running this file directly or via systemd ExecStart with the
# repo on PYTHONPATH; either way, find astro.capture.
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.capture.streaming import StreamingConfig, run
from astro.config import CameraConfig

CAM_V3W = 0
# Canonical camera name used for stage-1 brightness.csv path. Distinct
# from camera_name (which is the FITS CAMERA header / sensor model).
CAMERA = "eclipticam-v3w"
BUFFER_DIR = Path(os.environ.get("V3W_BUFFER_DIR",
                                 "/var/lib/eclipticam-buffer/v3w"))


def _param(env, cfg_val, fallback, cast):
    """Resolve a capture param: env var override → camera.json → fallback.
    Single source of truth is camera.json's `capture` block; env vars stay
    as a per-host escape hatch (e.g. a cold-night lens position)."""
    raw = os.environ.get(env)
    if raw is not None:
        return cast(raw)
    if cfg_val is not None:
        return cast(cfg_val)
    return cast(fallback)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    # camera.json is the single source of truth for v3w capture params
    # (pedestal, night exposure/gain, lens position). frames_root tracks
    # the NFS mount the rest of the pipeline uses. Env vars still override
    # any of these per-host. (Day capture uses the same lens position via
    # capture.py LENS_POSITION_V3W — keep them in step until unified.)
    cfg_v3w = CameraConfig.load("eclipticam-v3w")
    cap = cfg_v3w.get("capture") or {}
    frames_root = cfg_v3w.frames_root

    exposure_us = _param("V3W_EXPOSURE_US", cap.get("night_exposure_us"),
                         59_900_000, int)
    gain = _param("V3W_GAIN", cap.get("night_gain"), 1.0, float)
    lens_position = _param("V3W_LENS_POSITION", cap.get("lens_position"),
                           3.15, float)
    pedestal = _param("V3W_PEDESTAL", cfg_v3w.get("pedestal"), 4380, int)
    logging.info(f"capture params: exposure_us={exposure_us} gain={gain} "
                 f"lens_position={lens_position} pedestal={pedestal}")

    cfg = StreamingConfig(
        cam_idx=CAM_V3W,
        sensor_size=(2304, 1296),
        bayer_format="SRGGB10",
        bayer_pattern="RGGB",
        exposure_us=exposure_us,
        gain=gain,
        lens_position=lens_position,
        rotation_180=True,
        camera_name="imx708",
        buffer_dir=BUFFER_DIR,
        pedestal=pedestal,
        camera=CAMERA,
        frames_root=frames_root,
        mode="night",
    )
    reason = run(cfg)
    logging.info(f"exiting cleanly (reason={reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
