#!/usr/bin/env python3
"""eclipticam capture: every-10-min sun/moon imaging.

Day (sun_alt > -6 deg): auto-exposure JPEG.
Night (sun_alt <= -6 deg): forced 3s @ gain 1, captured as DNG and
converted in-place to Rice-compressed FITS (.fits.fz); DNG deleted.

Layout:
  ~/eclipticam-frames/day/YYYY-MM-DD/<cam>/HH/NNNN.jpg          (UTC date)
  ~/eclipticam-frames/night/YYYY-MM-DD/<cam>/HH/NNNN.fits.fz    (night-date = UTC - 12h)
HH is UTC hour; NNNN is per-(cam,HH) zero-padded counter.
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import rawpy
from PIL import Image, ExifTags
from astropy.io import fits

# OV5647 (v1) hardware shutter caps near 3.07 s in video config. To produce
# a 30 s integration on v1 we stream N raw frames via picamera2 and coadd
# them in RAM. Per-frame exposure stays at OV5647_FRAME_US (~3 s).
OV5647_FRAME_US = 3_000_000
V1_STACK_FRAMES = 10  # 10 x 3s ≈ 30s total integration

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "eclipticam-frames"  # day/<date>/<cam>/HH/NNNN.jpg, night/<night-date>/<cam>/HH/NNNN.fits.fz
STATE_DIR = Path("/var/lib/eclipticam")
STATE_FILE = STATE_DIR / "luminance.json"
LOCATION_FILE = HERE / "location.json"
LENS_POSITION_V3W = 0.0
NIGHT_SHUTTERS_US = [30_000_000]  # TEMP: 30s only for 1-min cadence
NIGHT_GAIN = 1.0
# 3s is the calibration / "no trails" frame used for the brightness state.
# 30s is for faint-star detection; expect ~9 px star trails near the celestial
# equator in the lower part of the v3w field. Trails are fine for first-night
# data; revisit (derot stacking vs longer exposure) after we see real frames.
BRIGHTNESS_SHUTTER_US = 3_000_000
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
    STATE_DIR.mkdir(parents=True, exist_ok=True)
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
    """Same metric, from FITS using stored EXPTIME + GAIN.

    Saturation guard: if the frame is clipped (mean at or near uint16
    ceiling) the lum calculation underestimates badly — a saturated 30s
    daytime frame returns ~0.002 which falsely reads as "night". Force a
    huge lum in that case so decide_mode trips the night→day transition
    immediately rather than sticking in night for hours of wasted 30s
    daylight captures."""
    with fits.open(path) as hdul:
        hdr = hdul[1].header
        data = hdul[1].data
    shutter_us = float(hdr["EXPTIME"]) * 1e6
    gain = float(hdr["GAIN"])
    mean = float(np.mean(data))
    if mean >= 64000:
        return 1.0  # forces above any LUMINANCE_NIGHT_EXIT
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


def shoot_night_one(camera_idx, out_path_fits, shutter_us, lens_position=None):
    """Force one long exposure, capture DNG, convert to .fits.fz, delete DNG + JPEG sidecar."""
    sidecar_jpg = out_path_fits.parent / (out_path_fits.stem + ".tmp.jpg")
    dng_path = sidecar_jpg.with_suffix(".dng")
    cmd = ["rpicam-still", "--camera", str(camera_idx),
           "--rotation", "180", "-o", str(sidecar_jpg),
           "-n", "-t", "500",
           "--shutter", str(shutter_us),
           "--gain", str(NIGHT_GAIN),
           "--raw"]
    if lens_position is not None:
        cmd += ["--autofocus-mode", "manual", "--lens-position", str(lens_position)]
    timeout_s = (shutter_us // 1_000_000) + 15
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if r.returncode != 0 or not dng_path.exists():
        print(f"night capture FAILED cam{camera_idx} {shutter_us}us -> {dng_path}", file=sys.stderr)
        print(r.stderr[-400:], file=sys.stderr)
        sidecar_jpg.unlink(missing_ok=True)
        return

    with rawpy.imread(str(dng_path)) as raw:
        bayer = raw.raw_image_visible.copy()
        pattern = "".join(chr(raw.color_desc[i]) for i in raw.raw_pattern.flatten())
    hdu = fits.CompImageHDU(data=bayer, compression_type="RICE_1")
    hdu.header["EXPTIME"] = shutter_us / 1e6
    hdu.header["GAIN"] = NIGHT_GAIN
    hdu.header["BAYERPAT"] = pattern
    hdu.header["DATE-OBS"] = datetime.now(timezone.utc).isoformat()
    hdu.header["CAMERA"] = "imx708" if camera_idx == CAM_V3W else "ov5647"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path_fits, overwrite=True)
    dng_path.unlink()
    sidecar_jpg.unlink(missing_ok=True)


def shoot_night_v1_stack(out_path_fits, frame_us=OV5647_FRAME_US,
                         n_frames=V1_STACK_FRAMES):
    """v1 long-integration via picamera2 streaming + in-RAM coadd.

    OV5647 max single shutter is ~3 s. We run a video pipeline at
    frame_us per frame and sum n_frames raw Bayer arrays into uint32.
    Total integration = frame_us * n_frames.

    Bayer pattern stored as SGBRG (OV5647 native, per project convention).
    """
    from picamera2 import Picamera2
    cam = Picamera2(camera_num=CAM_V1)
    try:
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            buffer_count=4,
        )
        cam.configure(cfg)
        cam.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "AnalogueGain": NIGHT_GAIN,
            "FrameDurationLimits": (frame_us, frame_us),
            "ExposureTime": frame_us,
        })
        cam.start()
        # Drop first frame — controls may not be applied yet.
        req = cam.capture_request()
        req.release()

        coadd = None
        t_start = datetime.now(timezone.utc)
        for _ in range(n_frames):
            req = cam.capture_request()
            try:
                bayer = req.make_array("raw").view(np.uint16)
            finally:
                req.release()
            if coadd is None:
                coadd = bayer.astype(np.uint32)
            else:
                coadd += bayer
        t_end = datetime.now(timezone.utc)
    finally:
        cam.stop()
        cam.close()

    # Sensor delivers data left-rotated 180 relative to rpicam-still output
    # (which we use --rotation 180). Match by flipping both axes.
    coadd = coadd[::-1, ::-1]
    hdu = fits.CompImageHDU(data=coadd.astype(np.uint32), compression_type="RICE_1")
    hdu.header["EXPTIME"] = frame_us * n_frames / 1e6
    hdu.header["FRAMEEXP"] = frame_us / 1e6
    hdu.header["NCOADD"] = n_frames
    hdu.header["GAIN"] = NIGHT_GAIN
    hdu.header["BAYERPAT"] = "SGBRG"
    hdu.header["DATE-OBS"] = t_start.isoformat()
    hdu.header["DATE-END"] = t_end.isoformat()
    hdu.header["CAMERA"] = "ov5647"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path_fits, overwrite=True)


def next_frame_path(hour_dir, ext):
    """hour_dir/NNNN.<ext> for the next free 4-digit counter."""
    hour_dir.mkdir(parents=True, exist_ok=True)
    used = []
    for f in hour_dir.glob(f"*.{ext}"):
        name = f.name.split(".", 1)[0]
        if name.isdigit():
            used.append(int(name))
    n = (max(used) + 1) if used else 1
    return hour_dir / f"{n:04d}.{ext}"


def shoot_night(camera_idx, hour_dir, lens_position=None):
    """Capture all NIGHT_SHUTTERS_US at this tick. Returns path of brightness frame.

    v1 (OV5647) can't do >3 s in a single exposure, so any shutter > OV5647_FRAME_US
    is delivered as a streamed coadd via shoot_night_v1_stack().
    """
    brightness_path = None
    for shutter_us in NIGHT_SHUTTERS_US:
        out_path = next_frame_path(hour_dir, "fits.fz")
        if camera_idx == CAM_V1 and shutter_us > OV5647_FRAME_US:
            n_frames = max(1, round(shutter_us / OV5647_FRAME_US))
            shoot_night_v1_stack(out_path, frame_us=OV5647_FRAME_US,
                                 n_frames=n_frames)
        else:
            shoot_night_one(camera_idx, out_path, shutter_us,
                            lens_position=lens_position)
        if shutter_us == BRIGHTNESS_SHUTTER_US and out_path.exists():
            brightness_path = out_path
    return brightness_path


def decide_mode(prev, last_lum):
    """Apply hysteresis + min-hold. prev = {'mode': 'day'|'night', 'hold': int, 'lum': float}.

    Returns new mode + new hold counter. Day is the default if no prev state.

    SATURATED_EXIT bypasses min-hold: a lum of 1.0 (from a saturated
    frame in scene_luminance_from_fits) means we're definitively in
    daylight — no point waiting MODE_HOLD_TICKS more 30s captures of
    pure white. Same shape but with no hold delay.
    """
    SATURATED_EXIT = 0.5  # any lum above this is an unambiguous "day"
    mode = prev.get("mode", "day")
    hold = int(prev.get("hold", MODE_HOLD_TICKS))
    if last_lum is None:
        return mode, hold + 1
    if mode == "night" and last_lum >= SATURATED_EXIT:
        return "day", 0  # bypass min-hold
    if hold < MODE_HOLD_TICKS:
        return mode, hold + 1
    if mode == "day" and last_lum < LUMINANCE_NIGHT_ENTER:
        return "night", 0
    if mode == "night" and last_lum > LUMINANCE_NIGHT_EXIT:
        return "day", 0
    return mode, hold + 1


def capture_tick():
    now = datetime.now(timezone.utc)
    utc_date = now.strftime("%Y-%m-%d")
    hh = now.strftime("%H")
    # Night-of date = UTC minus 12h (Europe/London noon-rollover convention).
    night_date = (now - timedelta(hours=12)).strftime("%Y-%m-%d")
    state = load_state()
    new_state = {}
    for cam_label, cam_idx, lp in [("v3w", CAM_V3W, LENS_POSITION_V3W),
                                    ("v1", CAM_V1, None)]:
        prev = state.get(cam_label, {})
        mode, hold = decide_mode(prev, prev.get("lum"))
        if mode == "night":
            hour_dir = FRAMES / "night" / night_date / cam_label / hh
            brightness_path = shoot_night(cam_idx, hour_dir, lens_position=lp)
            lum = scene_luminance_from_fits(brightness_path) if brightness_path else None
        else:
            hour_dir = FRAMES / "day" / utc_date / cam_label / hh
            out_path = next_frame_path(hour_dir, "jpg")
            shoot_day(cam_idx, out_path, lens_position=lp)
            lum = scene_luminance_from_jpeg(out_path) if out_path.exists() else None
        new_state[cam_label] = {"mode": mode, "hold": hold,
                                "lum": lum if lum is not None else prev.get("lum")}
    save_state(new_state)


if __name__ == "__main__":
    capture_tick()
