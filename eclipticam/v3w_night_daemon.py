#!/usr/bin/env python3
"""eclipticam-v3w-night — long-running streaming capture for v3w.

Started by systemd when eclipticam-capture.service flips v3w to
night mode; exits when:
  - SIGTERM (eclipticam-capture flipped back to day) → exit 0
  - frame mean crosses the dawn saturation threshold → exit 0
  - camera error → exit non-zero (systemd Restart=on-failure)

Writes Rice-compressed FITS to /dev/shm/eclipticam-v3w/. The
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

CAM_V3W = 0
EXPOSURE_US = int(os.environ.get("V3W_EXPOSURE_US", "59_900_000".replace("_", "")))
GAIN = float(os.environ.get("V3W_GAIN", "1.0"))
LENS_POSITION = float(os.environ.get("V3W_LENS_POSITION", "0.0"))
BUFFER_DIR = Path(os.environ.get("V3W_BUFFER_DIR",
                                 "/dev/shm/eclipticam-v3w"))
# IMX708 pedestal from eclipticam/camera.json — kept in sync there.
PEDESTAL = int(os.environ.get("V3W_PEDESTAL", "4380"))


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = StreamingConfig(
        cam_idx=CAM_V3W,
        sensor_size=(2304, 1296),
        bayer_format="SRGGB10",
        bayer_pattern="RGGB",
        exposure_us=EXPOSURE_US,
        gain=GAIN,
        lens_position=LENS_POSITION,
        rotation_180=True,
        camera_name="imx708",
        buffer_dir=BUFFER_DIR,
        pedestal=PEDESTAL,
    )
    reason = run(cfg)
    logging.info(f"exiting cleanly (reason={reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
