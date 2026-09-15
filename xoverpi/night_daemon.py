#!/usr/bin/env python3
"""xoverpi-night — night capture for the OV5647 at prime focus of the FirstScope.

Derived from eclipticam/v1_night_daemon.py, which is the estate's other OV5647
daemon, but with its central design decision REVERSED. That daemon exists to
beat the sensor's 3 s exposure ceiling by summing COADD_N=20 frames into a 60 s
effective exposure. That works behind a 53 deg lens where sidereal drift moves a
star a fraction of a pixel per second. It does NOT work here: at 0.963 arcsec/px
an equatorial star drifts 15.6 px/s, so a single 3 s sub already trails 47 px
and an unshifted 20-frame sum would smear ~940 px, a third of the frame.

So COADD_N defaults to 1 and subs are stored individually; shifting belongs at
stack time, where the smear is a known-PSF deconvolution (see camera.json
"drift"). Coadding is left available because near the celestial pole it becomes
viable again - 60 s smears only 10.6 px at Polaris - but it is off by default.

What this adds over the eclipticam daemon:

  * RUN TAG in every filename stem. This strand's founding lesson is the canon's
    2026-08-10 restart-collision bug, where per-run sequence numbering restarted
    at 1 after an abort and silently overwrote the previous run, destroying ~1000
    frames. A per-run UTC tag makes collision impossible by construction and
    records which run a frame came from.
  * ALTERNATING sub lengths. A box blur's MTF is a sinc with exact nulls where
    information is destroyed outright; nulls for one exposure length do not
    coincide with another's, so cycling lengths fills in each other's dead
    frequencies. Coded exposure in the time domain, for the price of a config
    change. (camera.json drift.vary_sub_length)
  * A PAUSE FILE. libcamera grants one process exclusive access to the camera,
    so capture and a focusing live view cannot coexist. Touch the pause file and
    the daemon releases the camera and waits; remove it and capture resumes.
  * A DISK GUARD. The NFS mount to bigstore is requested but not yet in place,
    so frames currently land on a 29 GB SD card. Binned at 3 s that is ~16 h of
    headroom, but the guard is what makes "currently local" safe rather than
    hopeful.

  bash: python3 night_daemon.py
  env:  XOVER_EXPOSURES (comma-separated seconds, cycled), XOVER_GAIN,
        XOVER_COADD_N, XOVER_BINNED (1/0), XOVER_MIN_FREE_GB, XOVER_ROTATE180
"""
import logging
import os
import shutil
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

CAMERA = "xoverpi"
RES_FULL = (2592, 1944)
RES_BIN = (1296, 972)
RAW_FORMAT = "SGBRG10"        # OV5647 native; confirmed against this camera
BAYERPAT = "SGBRG"

# MEASURED on this camera 2026-09-14, not quoted: identical across
# {video,still} x {full,binned}. Video mode does NOT buy a longer exposure.
EXPOSURE_MAX_US = 3_066_985

EXPOSURES = [float(x) for x in
             os.environ.get("XOVER_EXPOSURES", "1.0,2.0,3.0").split(",")]
GAIN = float(os.environ.get("XOVER_GAIN", 8.0))
COADD_N = int(os.environ.get("XOVER_COADD_N", 1))
BINNED = os.environ.get("XOVER_BINNED", "1") != "0"
MIN_FREE_GB = float(os.environ.get("XOVER_MIN_FREE_GB", 2.0))
ROTATE180 = os.environ.get("XOVER_ROTATE180", "0") == "1"

PAUSE_FILE = Path.home() / "xoverpi-capture.pause"
# One line of free text naming the CURRENT focuser setting, stamped into every
# frame as FOCUSPOS. A focus sweep that changes setting between nights is only
# analysable if each frame carries the setting it was taken at - otherwise the
# whole sweep reduces to "some frames, some focus". Set it with xoverpi/focus.py.
FOCUS_FILE = Path.home() / "xoverpi-focus"
SAT_LEVEL = 1023              # 10-bit data in a uint16 container
SAT_FRACTION = 0.9

_stop = False


def _on_signal(signum, _frame):
    global _stop
    logging.info(f"signal {signum}; stopping")
    _stop = True


def utcnow():
    return datetime.now(timezone.utc)


def write_fits(data, out_path, exp_us, n_coadd, t_start, t_end, mean, run_tag,
               focus):
    hdu = fits.CompImageHDU(data=data, compression_type="RICE_1")
    h = hdu.header
    h["EXPTIME"] = exp_us / 1e6 * n_coadd        # total integration (s)
    h["FRAMEEXP"] = exp_us / 1e6                 # single-frame exposure (s)
    h["NCOADD"] = n_coadd
    h["GAIN"] = GAIN
    h["BAYERPAT"] = BAYERPAT
    h["DATE-OBS"] = t_start.isoformat()
    h["DATE-END"] = t_end.isoformat()
    h["CAMERA"] = "ov5647"
    h["TELESCOP"] = "Celestron FirstScope 76/300"
    h["RUNTAG"] = run_tag
    h["FOCUSPOS"] = focus
    h["BINNING"] = 2 if BINNED else 1
    h["ROT180"] = ROTATE180
    h["MEAN"] = mean
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(tmp, overwrite=True)
    tmp.rename(out_path)        # atomic: a consumer never sees a partial frame


def read_focus() -> str:
    """Current focuser setting, or 'unset'. Read per frame, not per run, so a
    mid-night change is recorded on the frames it actually applies to."""
    try:
        v = FOCUS_FILE.read_text().strip()
        return v if v else "unset"
    except OSError:
        return "unset"


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def wait_while_paused():
    """Release the camera while PAUSE_FILE exists.

    libcamera is exclusive: rpicam-hello for focusing and this daemon cannot
    both hold the sensor. Returns True if we paused (caller must reopen).
    """
    if not PAUSE_FILE.exists():
        return False
    logging.info(f"{PAUSE_FILE} present; releasing camera and waiting")
    while PAUSE_FILE.exists() and not _stop:
        time.sleep(5)
    logging.info("pause cleared; resuming")
    return True


def open_camera():
    res = RES_BIN if BINNED else RES_FULL
    cam = Picamera2()
    cam.configure(cam.create_video_configuration(
        raw={"size": res, "format": RAW_FORMAT},
        main={"size": (640, 480), "format": "RGB888"},
        buffer_count=4))
    cam.set_controls({"AeEnable": False, "AwbEnable": False,
                      "AnalogueGain": GAIN})
    cam.start()
    cam.capture_request().release()      # drop first: controls may not be live
    return cam


def set_exposure(cam, exp_us):
    """Apply an exposure and wait until the sensor is actually delivering it.

    FrameDurationLimits must be set alongside ExposureTime or the request is
    silently clamped to the current frame period - the OV5647 gotcha that makes
    a long shutter look like it was ignored.
    """
    cam.set_controls({"ExposureTime": exp_us,
                      "FrameDurationLimits": (exp_us, exp_us)})
    # The FIRST control change after start() takes several frames to land - a
    # 6-attempt limit let frame 1 of a run be written at the sensor's startup
    # exposure instead of the requested one (measured 2026-09-14: 1 ms where
    # 4 ms was asked). The header stays truthful either way because we record
    # the metadata value, not the request, but a stack wants the exposure it
    # asked for. Be patient, and say so when it still does not converge.
    actual = 0
    for _ in range(20):
        req = cam.capture_request()
        actual = req.get_metadata().get("ExposureTime", 0)
        req.release()
        if abs(actual - exp_us) <= max(200, exp_us * 0.05):
            return actual
    logging.warning(f"exposure did not converge: asked {exp_us} us, "
                    f"sensor delivering {actual} us; recording the actual")
    return actual


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    cfg = CameraConfig.load(CAMERA)
    frames_root = cfg.frames_root
    frames_root.mkdir(parents=True, exist_ok=True)

    run_tag = utcnow().strftime("%Y%m%dT%H%M%SZ")
    exposures_us = []
    for s in EXPOSURES:
        us = int(s * 1e6)
        if us > EXPOSURE_MAX_US:
            logging.warning(f"{s}s exceeds the measured {EXPOSURE_MAX_US/1e6:.2f}s "
                            f"ceiling; clamping")
            us = EXPOSURE_MAX_US
        exposures_us.append(us)

    logging.info(f"run {run_tag}: exposures {[u/1e6 for u in exposures_us]}s, "
                 f"gain {GAIN}, coadd {COADD_N}, "
                 f"{'binned 2x2' if BINNED else 'full-res'}, root {frames_root}")

    cam = open_camera()
    seq = 0
    i = 0
    try:
        while not _stop:
            if wait_while_paused():
                cam.stop(); cam.close()
                if _stop:
                    break
                cam = open_camera()

            if free_gb(frames_root) < MIN_FREE_GB:
                logging.error(f"only {free_gb(frames_root):.1f} GB free at "
                              f"{frames_root} (< {MIN_FREE_GB}); stopping")
                break

            focus = read_focus()
            exp_us = exposures_us[i % len(exposures_us)]
            i += 1
            actual_us = set_exposure(cam, exp_us)

            acc = None
            t_start = None
            for _ in range(COADD_N):
                req = cam.capture_request()
                try:
                    bayer = req.make_array("raw").view(np.uint16).copy()
                finally:
                    req.release()
                if ROTATE180:
                    # NB a 180 rotation of a Bayer mosaic changes the pattern
                    # (SGBRG -> GRBG). Only enable this with a BAYERPAT to match.
                    bayer = bayer[::-1, ::-1]
                now = utcnow()
                if acc is None:
                    acc = bayer.astype(np.uint32)
                    t_start = now
                else:
                    acc += bayer

            out = np.clip(acc, 0, 65535).astype(np.uint16)
            mean = float(out.mean())
            if mean >= SAT_LEVEL * COADD_N * SAT_FRACTION:
                logging.info(f"mean {mean:.0f} saturated (dawn); exit")
                break

            hh = now.strftime("%H")
            night_dir = frames_root / "night" / night_of(now) / hh
            night_dir.mkdir(parents=True, exist_ok=True)
            seq += 1
            out_path = night_dir / f"{run_tag}-{seq:05d}.fits.fz"
            write_fits(out, out_path, actual_us, COADD_N, t_start, now,
                       mean, run_tag, focus)
            logging.info(f"wrote {out_path.name} exp={actual_us/1e6:.2f}s "
                         f"focus={focus} mean={mean:.1f} "
                         f"free={free_gb(frames_root):.1f}GB")
    finally:
        try:
            cam.stop(); cam.close()
        except Exception:
            pass
    logging.info(f"run {run_tag} exiting cleanly after {seq} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
