#!/usr/bin/env python3
"""eclipticam capture: every-10-min sun/moon imaging.

Day (sun_alt > -6 deg): auto-exposure JPEG.
Night (sun_alt <= -6 deg): forced 3s @ gain 1, captured as DNG and
converted in-place to Rice-compressed FITS (.fits.fz); DNG deleted.

Layout: ~/eclipticam-frames/series/YYYY-MM-DD/<camera>/HHMM.{jpg,fits.fz}
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import rawpy
from astropy.coordinates import EarthLocation, AltAz, get_sun
from astropy.io import fits
from astropy.time import Time
import astropy.units as u

HOME = Path.home()
FRAMES = HOME / "eclipticam-frames" / "series"
LOCATION = HOME / "eclipticam-capture" / "location.json"
LENS_POSITION_V3W = 0.0
NIGHT_SUN_ALT_DEG = -6.0
NIGHT_SHUTTER_US = 3_000_000
NIGHT_GAIN = 1.0

CAM_V3W = 0
CAM_V1 = 1


def load_location():
    c = json.loads(LOCATION.read_text())
    return EarthLocation(lat=c["lat_deg"] * u.deg,
                         lon=c["lon_deg"] * u.deg,
                         height=c["height_m"] * u.m)


def sun_alt_now():
    loc = load_location()
    t = Time(datetime.now(timezone.utc))
    return float(get_sun(t).transform_to(AltAz(obstime=t, location=loc)).alt.deg)


def shoot_day(camera_idx, out_path, lens_position=None, timeout_ms=1500):
    cmd = ["rpicam-still", "--camera", str(camera_idx),
           "--rotation", "180", "-o", str(out_path),
           "-n", "-t", str(timeout_ms)]
    if lens_position is not None:
        cmd += ["--autofocus-mode", "manual", "--lens-position", str(lens_position)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not out_path.exists():
        print(f"capture FAILED cam{camera_idx} -> {out_path}", file=sys.stderr)
        print(r.stderr[-400:], file=sys.stderr)


def shoot_night(camera_idx, out_path_fits, lens_position=None):
    """Force 3s @ gain 1, capture DNG, convert to .fits.fz, delete DNG."""
    dng_path = out_path_fits.with_suffix(".dng")
    jpg_path = out_path_fits.with_suffix(".jpg")
    cmd = ["rpicam-still", "--camera", str(camera_idx),
           "--rotation", "180", "-o", str(jpg_path),
           "-n", "-t", "500",
           "--shutter", str(NIGHT_SHUTTER_US),
           "--gain", str(NIGHT_GAIN),
           "--raw"]
    if lens_position is not None:
        cmd += ["--autofocus-mode", "manual", "--lens-position", str(lens_position)]
    timeout_s = (NIGHT_SHUTTER_US // 1_000_000) + 15
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if r.returncode != 0 or not dng_path.exists():
        print(f"night capture FAILED cam{camera_idx} -> {dng_path}", file=sys.stderr)
        print(r.stderr[-400:], file=sys.stderr)
        return

    with rawpy.imread(str(dng_path)) as raw:
        bayer = raw.raw_image_visible.copy()
        pattern = "".join(chr(raw.color_desc[i]) for i in raw.raw_pattern.flatten())
    hdu = fits.CompImageHDU(data=bayer, compression_type="RICE_1")
    hdu.header["EXPTIME"] = NIGHT_SHUTTER_US / 1e6
    hdu.header["GAIN"] = NIGHT_GAIN
    hdu.header["BAYERPAT"] = pattern
    hdu.header["DATE-OBS"] = datetime.now(timezone.utc).isoformat()
    hdu.header["CAMERA"] = "imx708" if camera_idx == CAM_V3W else "ov5647"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path_fits, overwrite=True)
    dng_path.unlink()


def capture_tick():
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H%M")
    night = sun_alt_now() <= NIGHT_SUN_ALT_DEG
    for cam_label, cam_idx, lp in [("v3w", CAM_V3W, LENS_POSITION_V3W),
                                    ("v1", CAM_V1, None)]:
        out_dir = FRAMES / day / cam_label
        out_dir.mkdir(parents=True, exist_ok=True)
        if night:
            shoot_night(cam_idx, out_dir / f"{hhmm}.fits.fz", lens_position=lp)
        else:
            shoot_day(cam_idx, out_dir / f"{hhmm}.jpg", lens_position=lp)


if __name__ == "__main__":
    capture_tick()
