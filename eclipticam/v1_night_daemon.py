#!/usr/bin/env python3
"""eclipticam-v1-night — night capture for the v1 (OV5647) camera.

v1 is a fixed 3 s single-exposure ceiling (OV5647), so — like astrocam's
8×1.2 s coadd — we sum N frames into a longer effective exposure. Default
COADD_N=20 → 20×3 s = 60 s FITS, matching a "1 minute exposure". Writes
Rice-compressed .fits.fz to the v1 night tree, same flow as v3w. NO stage-3
processing (capture + coadd + store only).

Runs on cam1 (OV5647), independent of cam0 (v3w streaming). Started manually
or by a systemd unit at dusk; exits on SIGTERM or a saturation (dawn) guard.

  bash: python3 v1_night_daemon.py         # defaults (20×3s coadd)
  env:  V1_COADD_N, V1_EXPOSURE_US, V1_GAIN override.
"""
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits
from picamera2 import Picamera2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from astro.nightdir import night_of          # noqa: E402
from astro.config import CameraConfig         # noqa: E402

CAM_V1 = 1
CAMERA = "eclipticam-v1"
RESOLUTION = (2592, 1944)
RAW_FORMAT = "SGBRG10"           # OV5647 native (camera.json); rpicam DNG reports GRBG
BAYERPAT = "SGBRG"

COADD_N = int(os.environ.get("V1_COADD_N", 20))          # 20 × 3 s = 60 s
EXPOSURE_US = int(os.environ.get("V1_EXPOSURE_US", 3_000_000))
GAIN = float(os.environ.get("V1_GAIN", 8.0))

# Dawn guard: uint16 coadd ceiling is 65535; a coadd mean past this fraction of
# it means daylight has saturated the frames — stop and let dusk restart it.
SAT_FRACTION = 0.9

_stop = False


def _on_signal(signum, _frame):
    global _stop
    logging.info(f"signal {signum}; stopping")
    _stop = True


def utcnow():
    return datetime.now(timezone.utc)


def write_fits(coadd, out_path, n_coadd, t_start, t_end, mean):
    hdu = fits.CompImageHDU(data=coadd, compression_type="RICE_1")
    h = hdu.header
    h["EXPTIME"] = EXPOSURE_US / 1e6 * n_coadd     # total integration (s)
    h["FRAMEEXP"] = EXPOSURE_US / 1e6              # single-frame exposure
    h["NCOADD"] = n_coadd
    h["GAIN"] = GAIN
    h["BAYERPAT"] = BAYERPAT
    h["DATE-OBS"] = t_start.isoformat()
    h["DATE-END"] = t_end.isoformat()
    h["CAMERA"] = "ov5647"
    h["MEAN"] = mean
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(tmp, overwrite=True)
    tmp.rename(out_path)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    cfg_v1 = CameraConfig.load(CAMERA)
    frames_root = cfg_v1.frames_root      # ~/eclipticam-frames
    logging.info(f"v1 night: coadd {COADD_N}×{EXPOSURE_US/1e6:.1f}s "
                 f"= {COADD_N*EXPOSURE_US/1e6:.0f}s, gain {GAIN}")

    cam = Picamera2(camera_num=CAM_V1)
    vcfg = cam.create_video_configuration(
        raw={"size": RESOLUTION, "format": RAW_FORMAT},
        main={"size": (640, 480), "format": "RGB888"},
        buffer_count=4,
    )
    cam.configure(vcfg)
    cam.set_controls({
        "AeEnable": False, "AwbEnable": False,
        "AnalogueGain": GAIN,
        "FrameDurationLimits": (EXPOSURE_US, EXPOSURE_US),
        "ExposureTime": EXPOSURE_US,
    })
    cam.start()
    # Drop first frame — controls may not be applied yet.
    cam.capture_request().release()

    coadd = None
    n = 0
    t_start = None
    dtype_max = 65535
    try:
        while not _stop:
            req = cam.capture_request()
            try:
                bayer = req.make_array("raw").view(np.uint16).copy()
            finally:
                req.release()
            bayer = bayer[::-1, ::-1]          # rotation 180 (match rpicam)
            now = utcnow()
            if coadd is None:
                coadd = bayer.astype(np.uint32)
                n = 1
                t_start = now
            else:
                coadd += bayer
                n += 1
            if n >= COADD_N:
                out = coadd.astype(np.uint16) if coadd.max() <= dtype_max \
                    else np.clip(coadd, 0, dtype_max).astype(np.uint16)
                mean = float(out.mean())
                if mean >= dtype_max * SAT_FRACTION:
                    logging.info(f"coadd mean {mean:.0f} saturated (dawn); exit")
                    break
                # v1 night tree (percam layout, like the legacy path):
                # <root>/night/<night>/v1/HH/NNNN.fits.fz
                hh = now.strftime("%H")
                night_dir = (frames_root / "night" / night_of(now) / "v1" / hh)
                night_dir.mkdir(parents=True, exist_ok=True)
                used = [int(p.stem.split(".")[0]) for p in night_dir.glob("*.fits.fz")
                        if p.stem.split(".")[0].isdigit()]
                seq = (max(used) + 1) if used else 1
                write_fits(out, night_dir / f"{seq:04d}.fits.fz",
                           n, t_start, now, mean)
                logging.info(f"wrote {night_dir}/{seq:04d}.fits.fz mean={mean:.0f}")
                coadd = None
                n = 0
                t_start = None
    finally:
        cam.stop()
    logging.info("exiting cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
