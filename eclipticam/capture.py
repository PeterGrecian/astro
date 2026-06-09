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
from PIL import Image, ExifTags
from astropy.io import fits

HOME = Path.home()
FRAMES = HOME / "eclipticam-frames" / "series"
STATE_FILE = HOME / "eclipticam-capture" / "luminance.json"
LENS_POSITION_V3W = 0.0
NIGHT_SHUTTER_US = 3_000_000
NIGHT_GAIN = 1.0
# Hysteresis on scene_luminance = mean_pixel / (shutter_us * gain).
# DAY -> NIGHT when below the dark threshold for MODE_HOLD_TICKS ticks.
# NIGHT -> DAY when above the light threshold for MODE_HOLD_TICKS ticks.
# 10x gap between thresholds prevents flapping near twilight.
LUMINANCE_NIGHT_ENTER = 0.0005
LUMINANCE_NIGHT_EXIT = 0.005
MODE_HOLD_TICKS = 3  # min ticks (30 min) before mode can switch back
_EXIF_EXPOSURE = 33434
_EXIF_ISO = 34855

CAM_V3W = 0
CAM_V1 = 1


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def scene_luminance_from_jpeg(path):
    """Mean pixel / (shutter_us * gain). Smaller = darker."""
    try:
        ifd = Image.open(path).getexif().get_ifd(0x8769)
        shutter_us = float(ifd[_EXIF_EXPOSURE]) * 1e6
        iso = float(ifd[_EXIF_ISO])
    except Exception:
        return None
    mean = float(np.array(Image.open(path).convert("L")).mean())
    if shutter_us * iso <= 0:
        return None
    return mean / (shutter_us * iso / 100.0)  # iso/100 = gain


def scene_luminance_from_fits(path):
    """Same metric, from FITS using stored EXPTIME + GAIN."""
    with fits.open(path) as hdul:
        hdr = hdul[1].header
        data = hdul[1].data
    shutter_us = float(hdr["EXPTIME"]) * 1e6
    gain = float(hdr["GAIN"])
    mean = float(np.mean(data))
    if shutter_us * gain <= 0:
        return None
    return mean / (shutter_us * gain)


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
    """Force 3s @ gain 1, capture DNG, convert to .fits.fz, delete DNG + JPEG sidecar."""
    # rpicam-still always writes the -o file; we ask for a .jpg sidecar we'll discard.
    sidecar_jpg = out_path_fits.parent / (out_path_fits.stem + ".tmp.jpg")
    dng_path = sidecar_jpg.with_suffix(".dng")
    cmd = ["rpicam-still", "--camera", str(camera_idx),
           "--rotation", "180", "-o", str(sidecar_jpg),
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
        sidecar_jpg.unlink(missing_ok=True)
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
    sidecar_jpg.unlink(missing_ok=True)


def decide_mode(prev, last_lum):
    """Apply hysteresis + min-hold. prev = {'mode': 'day'|'night', 'hold': int, 'lum': float}.

    Returns new mode + new hold counter. Day is the default if no prev state.
    """
    mode = prev.get("mode", "day")
    hold = int(prev.get("hold", MODE_HOLD_TICKS))
    if last_lum is None:
        return mode, hold + 1
    if hold < MODE_HOLD_TICKS:
        return mode, hold + 1
    if mode == "day" and last_lum < LUMINANCE_NIGHT_ENTER:
        return "night", 0
    if mode == "night" and last_lum > LUMINANCE_NIGHT_EXIT:
        return "day", 0
    return mode, hold + 1


def capture_tick():
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H%M")
    state = load_state()
    new_state = {}
    for cam_label, cam_idx, lp in [("v3w", CAM_V3W, LENS_POSITION_V3W),
                                    ("v1", CAM_V1, None)]:
        out_dir = FRAMES / day / cam_label
        out_dir.mkdir(parents=True, exist_ok=True)
        prev = state.get(cam_label, {})
        mode, hold = decide_mode(prev, prev.get("lum"))
        if mode == "night":
            out_path = out_dir / f"{hhmm}.fits.fz"
            shoot_night(cam_idx, out_path, lens_position=lp)
            lum = scene_luminance_from_fits(out_path) if out_path.exists() else None
        else:
            out_path = out_dir / f"{hhmm}.jpg"
            shoot_day(cam_idx, out_path, lens_position=lp)
            lum = scene_luminance_from_jpeg(out_path) if out_path.exists() else None
        new_state[cam_label] = {"mode": mode, "hold": hold,
                                "lum": lum if lum is not None else prev.get("lum")}
    save_state(new_state)


if __name__ == "__main__":
    capture_tick()
