#!/usr/bin/env python3
"""eclipticam-hq16-night — streaming night capture for the HQ 16 mm camera.

The IMX477 HQ camera on cam1 (first light 2026-10-13), beside v3w on cam0.
Same lifecycle as v3w_night_daemon.py: started and stopped by
eclipticam-capture.service on the sun-altitude switch; exits 0 on SIGTERM
or dawn saturation, non-zero on camera failure (systemd restarts it).

Writes Rice-compressed FITS to /var/lib/eclipticam-buffer/hq16/; a second
instance of v3w_uploader.py (V3W_SUBCAM=hq16) drains it to the night tree.
camera.json (eclipticam-hq16) is the single source of truth for params.
"""
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.capture.streaming import StreamingConfig, run
from astro.config import CameraConfig

CAMERA = "eclipticam-hq16"
BUFFER_DIR = Path(os.environ.get("HQ_BUFFER_DIR",
                                 "/mnt/ssd/eclipticam-buffer/hq16"))
BUFFER_MOUNT = Path(os.environ.get("HQ_BUFFER_MOUNT", "/mnt/ssd"))


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg_hq = CameraConfig.load(CAMERA)
    cap = cfg_hq.get("capture") or {}
    exposure_us = int(os.environ.get("HQ_EXPOSURE_US",
                                     cap.get("night_exposure_us", 59_900_000)))
    gain = float(os.environ.get("HQ_GAIN", cap.get("night_gain", 1.0)))
    width, height = cfg_hq.get("resolution")
    position_index = cfg_hq.get("position_index")
    logging.info(f"capture params: exposure_us={exposure_us} gain={gain} "
                 f"position_index={position_index}")

    cfg = StreamingConfig(
        cam_idx=cfg_hq.get("cam_idx", 1),
        sensor_size=(width, height),
        bayer_format=cfg_hq.get("bayer"),
        bayer_pattern="RGGB",
        exposure_us=exposure_us,
        gain=gain,
        lens_position=None,        # manual lens: no VCM
        # The driver already turns the image upright (dtoverlay rotation=0);
        # see camera.json rotate_180_notes.
        rotation_180=bool(cfg_hq.get("rotate_180")),
        camera_name="imx477",
        buffer_dir=BUFFER_DIR,
        pedestal=int(cfg_hq.get("pedestal")),
        black_level=cfg_hq.get("black_level"),
        camera=CAMERA,
        frames_root=cfg_hq.frames_root,
        mode="night",
        position_index=position_index,
        sample_bits=12,
        buffer_count=int(cap.get("buffer_count", 4)),
        buffer_mount=BUFFER_MOUNT,
    )
    reason = run(cfg)
    if reason == "capture_failed":
        logging.error(f"exiting on capture failure (reason={reason})")
        return 1
    logging.info(f"exiting cleanly (reason={reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
