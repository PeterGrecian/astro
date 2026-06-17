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
# Near-60s exposure at 1-min cadence: 55 s leaves ~5 s for libcamera
# warm-up + write before the next timer fire. The IMX708 (v3w) ceiling
# is ~112 s in still-config so we're well inside it. Saturation tends
# to land around twilight where it's expected anyway — the anchor-band
# gate downstream rejects bright frames.
NIGHT_SHUTTERS_US = [55_000_000]
NIGHT_GAIN = 1.0
BRIGHTNESS_SHUTTER_US = 55_000_000  # same frame drives both stack + brightness
# Mode decision is purely sun-altitude. Brightness measurements are
# still recorded per frame (drives frame-quality gating downstream and
# the per-night brightness plot), but they do NOT decide whether to
# enter night — car headlights, the moon, AE wobble, and cloud edges
# all confuse per-frame brightness, while sun altitude is a hard
# physical signal we can compute exactly from time + location.
# Asymmetric thresholds give natural hysteresis. -14° is well into
# astronomical twilight (sun far enough below the horizon that v3w's
# 55s exposure survives without saturating); -10° is end-of-nautical-
# twilight, captures all dark hours before any chance of saturation.
SUN_ALT_NIGHT_DEG = -14.0
SUN_ALT_DAY_DEG = -10.0
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

    Saturation clamp: if the frame is clipped (mean at or near uint16
    ceiling) the per_s = mean / (shutter * gain) metric underestimates
    badly — a saturated 30s frame returns ~0.002 even though it's
    pegged. Clamp to 1.0 so saturation shows up as "definitely bright"
    in state.json and logs. (The controller doesn't decide mode from
    lum any more — sun altitude does — but recording an honest 1.0
    keeps the observational signal readable.)"""
    with fits.open(path) as hdul:
        hdr = hdul[1].header
        data = hdul[1].data
    shutter_us = float(hdr["EXPTIME"]) * 1e6
    gain = float(hdr["GAIN"])
    mean = float(np.mean(data))
    if mean >= 64000:
        return 1.0  # saturated; observational clamp
    if shutter_us * gain <= 0:
        return None
    return mean / (shutter_us * gain)



# --- v3w streaming daemon coordination -------------------------------
# The v3w night capture is owned by eclipticam-v3w-night.service
# (Picamera2 streaming, see astro/capture/streaming.py). This script
# is invoked every minute by eclipticam-capture.timer; on each tick it
# only ensures the streaming service is in the right state for the
# current mode. v3w night frames themselves are written by the
# streaming daemon, not here.
V3W_BUFFER_DIR = Path("/var/lib/eclipticam-buffer/v3w")
V3W_NIGHT_SERVICE = "eclipticam-v3w-night.service"


def _systemctl(*args):
    """Best-effort systemctl invocation; never raises."""
    try:
        return subprocess.run(["systemctl", *args],
                              capture_output=True, text=True, timeout=10)
    except Exception as e:
        print(f"systemctl {' '.join(args)}: {e}", file=sys.stderr)
        return None


def ensure_v3w_streaming_running():
    r = _systemctl("is-active", "--quiet", V3W_NIGHT_SERVICE)
    if r is None or r.returncode != 0:
        _systemctl("start", V3W_NIGHT_SERVICE)


def ensure_v3w_streaming_stopped():
    r = _systemctl("is-active", "--quiet", V3W_NIGHT_SERVICE)
    if r is not None and r.returncode == 0:
        _systemctl("stop", V3W_NIGHT_SERVICE)


def streaming_v3w_lum():
    """Read the most-recent per_s from the streaming daemon's
    brightness.csv (in tmpfs) for recording into state.json. Mode is
    now decided from sun altitude — this is observational only.

    Saturation clamp: if the latest frame's mean is at/near uint16
    ceiling, per_s collapses to a tiny number and looks like deep
    night in the state file. Clamp to 1.0 so saturation is honest.
    CSV columns: epoch_ms,mean,exposure_us,gain,per_s.
    """
    bf = V3W_BUFFER_DIR / "brightness.csv"
    if not bf.exists() or bf.stat().st_size == 0:
        return None
    try:
        lines = [ln for ln in bf.read_text().splitlines()
                 if ln and not ln.startswith("epoch_ms")]
        if not lines:
            return None
        parts = lines[-1].split(",")
        mean = float(parts[1])
        if mean >= 64000:
            return 1.0  # saturated; observational clamp
        return float(parts[4])
    except Exception:
        return None

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

    The brightness frame is preferred at BRIGHTNESS_SHUTTER_US (a short
    no-trails reference), but if that shutter isn't in NIGHT_SHUTTERS_US
    today we fall back to the longest available frame — otherwise the
    luminance state never updates and the mode machine gets stuck.
    """
    brightness_path = None
    fallback_path = None
    for shutter_us in NIGHT_SHUTTERS_US:
        out_path = next_frame_path(hour_dir, "fits.fz")
        if camera_idx == CAM_V1 and shutter_us > OV5647_FRAME_US:
            n_frames = max(1, round(shutter_us / OV5647_FRAME_US))
            shoot_night_v1_stack(out_path, frame_us=OV5647_FRAME_US,
                                 n_frames=n_frames)
        else:
            shoot_night_one(camera_idx, out_path, shutter_us,
                            lens_position=lens_position)
        if out_path.exists():
            if shutter_us == BRIGHTNESS_SHUTTER_US:
                brightness_path = out_path
            else:
                fallback_path = out_path
    return brightness_path or fallback_path


_LOCATION = None  # lazily loaded; sun_altitude_deg reuses it across ticks


def sun_altitude_deg(when=None):
    """Sun altitude in degrees at the camera's location at UTC `when`
    (default now). Returns None if location.json or ephem are missing —
    decide_mode then ignores the gate (degrades to lum-only)."""
    global _LOCATION
    if _LOCATION is None:
        try:
            _LOCATION = json.loads(LOCATION_FILE.read_text())
        except Exception:
            _LOCATION = {}
    if "lat_deg" not in _LOCATION or "lon_deg" not in _LOCATION:
        return None
    try:
        import ephem
    except ImportError:
        return None
    obs = ephem.Observer()
    obs.lat = str(_LOCATION["lat_deg"])
    obs.lon = str(_LOCATION["lon_deg"])
    obs.date = (when or datetime.now(timezone.utc)).strftime(
        "%Y/%m/%d %H:%M:%S")
    obs.pressure = 0  # no refraction
    return float(ephem.Sun(obs).alt) * 180.0 / 3.141592653589793


def decide_mode(prev, sun_alt_deg):
    """Mode is a pure function of sun altitude.

    sun_alt < SUN_ALT_NIGHT_DEG  → night
    sun_alt > SUN_ALT_DAY_DEG    → day
    in-between                    → keep prev (asymmetric thresholds
                                     give natural hysteresis with no
                                     flap, no flip-back guard, no
                                     hold counter).

    prev = {'mode': 'day'|'night', ...} (other fields ignored).
    Returns (mode, hold) where hold is just an incrementing tick
    counter — kept for state-file backwards compatibility; nothing
    reads it as a control input any more.

    If sun_alt_deg is None (location.json or ephem missing), default
    to day. This is the safe fall-back: a stuck day mode never starts
    the streaming daemon at all, no chance of writing pegged frames.
    """
    mode = prev.get("mode", "day")
    hold = int(prev.get("hold", 0)) + 1
    if sun_alt_deg is None:
        return "day", hold
    if sun_alt_deg < SUN_ALT_NIGHT_DEG:
        return "night", hold
    if sun_alt_deg > SUN_ALT_DAY_DEG:
        return "day", hold
    return mode, hold


def capture_tick():
    now = datetime.now(timezone.utc)
    utc_date = now.strftime("%Y-%m-%d")
    hh = now.strftime("%H")
    # Night-of date = UTC minus 12h (Europe/London noon-rollover convention).
    night_date = (now - timedelta(hours=12)).strftime("%Y-%m-%d")
    # Per-camera capture policy. v3w runs in both day and night so its
    # state machine drives the cover/exposure decisions; v1 stays
    # day-only because its 3 s single-exposure ceiling makes useful
    # night astronomy hard at the 1-min cadence (no time for a 10x
    # streamed coadd plus v3w's 55 s exposure inside 60 s). Revisit
    # when v1 gets its own role (e.g. solar imaging during the day).
    state = load_state()
    new_state = {}
    # Mode is purely sun-altitude (see decide_mode). Brightness is
    # still measured and recorded per frame — drives frame-quality
    # gating downstream, populates the per-night brightness plot, and
    # lives in state.json as observation — but it does NOT decide
    # mode. Sun altitude is a hard physical signal; per-frame
    # brightness is confused by headlights, moon, AE wobble, clouds.
    sun_alt = sun_altitude_deg(now)
    # v3w first: its mode gates whether v1 even bothers shooting.
    v3w_prev = state.get("v3w", {})
    v3w_mode, v3w_hold = decide_mode(v3w_prev, sun_alt_deg=sun_alt)
    if v3w_mode == "night":
        # Streaming daemon owns the camera. Don't touch cam0 here.
        ensure_v3w_streaming_running()
        lum = streaming_v3w_lum()
    else:
        ensure_v3w_streaming_stopped()
        hour_dir = FRAMES / "day" / utc_date / "v3w" / hh
        out_path = next_frame_path(hour_dir, "jpg")
        shoot_day(CAM_V3W, out_path, lens_position=LENS_POSITION_V3W)
        lum = scene_luminance_from_jpeg(out_path) if out_path.exists() else None
    new_state["v3w"] = {"mode": v3w_mode, "hold": v3w_hold,
                        "lum": lum if lum is not None else v3w_prev.get("lum")}

    # v1 is day-only hardware; only shoot when v3w confirms it's day.
    # In v3w-night the scene is dark, so a v1 day-mode JPG is just
    # noise — skip it. v1 state freezes so its hysteresis resumes
    # cleanly when day returns.
    v1_prev = state.get("v1", {})
    v1_mode, v1_hold = decide_mode(v1_prev, sun_alt_deg=sun_alt)
    if v3w_mode == "day":
        hour_dir = FRAMES / "day" / utc_date / "v1" / hh
        out_path = next_frame_path(hour_dir, "jpg")
        shoot_day(CAM_V1, out_path, lens_position=None)
        v1_lum = scene_luminance_from_jpeg(out_path) if out_path.exists() else None
    else:
        v1_lum = None
    new_state["v1"] = {"mode": v1_mode, "hold": v1_hold,
                       "lum": v1_lum if v1_lum is not None else v1_prev.get("lum")}
    save_state(new_state)


if __name__ == "__main__":
    capture_tick()
