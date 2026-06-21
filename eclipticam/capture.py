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
from PIL import Image

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "eclipticam-frames"  # day/<date>/<cam>/HH/NNNN.jpg, night/<night-date>/<cam>/HH/NNNN.fits.fz
STATE_DIR = Path("/var/lib/eclipticam")
STATE_FILE = STATE_DIR / "luminance.json"
LOCATION_FILE = HERE / "location.json"
# IMX708 manual focus is in DIOPTRES (1/metres); 0.0 is NOMINALLY infinity
# but is badly soft on this Module 3 Wide — measured 2026-06-21: rooftop/
# distant-tree sharpness (laplacian variance) rose ~10x from lens 0.0 (12)
# to ~3.0-3.2 (119). Autofocus on an infinity scene settled at 3.07-3.25
# across 5 runs (mean ~3.15) at 42 C sensor temp. So TRUE infinity is ~3.15,
# not 0.0 — every prior night star/moon frame was out of focus. Set to 3.15.
# TODO (AF-feeds-night): day mode should autofocus and record the lens
# position to a state file; night reads it so focus tracks temperature
# drift (focus shifts with lens/sensor temp, day-vs-night ~15-20 C). 3.15
# is the fixed fallback measured warm; verify it holds on a cold night.
LENS_POSITION_V3W = 3.15
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


# Night threshold is config-driven: read the v3w camera.json `state`
# override once so a single source of truth governs when night starts.
# Falls back to the module constant if the config or key is absent.
# v3w gates the whole pipeline; v1 is day-only so it inherits the same
# threshold (its night mode never does astronomy anyway).
_V3W_CAMERA_JSON = HERE.parent / "eclipticam-v3w" / "camera.json"
_NIGHT_DEG = None  # lazily resolved


def night_threshold_deg():
    """The sun altitude (deg) below which v3w switches to night, from
    eclipticam-v3w/camera.json `state.sun_altitude_night_deg`, falling
    back to the module SUN_ALT_NIGHT_DEG constant."""
    global _NIGHT_DEG
    if _NIGHT_DEG is None:
        _NIGHT_DEG = SUN_ALT_NIGHT_DEG
        try:
            state = json.loads(_V3W_CAMERA_JSON.read_text()).get("state", {})
            v = state.get("sun_altitude_night_deg")
            if v is not None:
                _NIGHT_DEG = float(v)
        except Exception:
            pass
    return _NIGHT_DEG


def decide_mode(prev, sun_alt_deg, night_deg=None, day_deg=None):
    """Mode is a pure function of sun altitude.

    sun_alt < night_deg  → night
    sun_alt > day_deg     → day
    in-between            → keep prev (asymmetric thresholds give
                             natural hysteresis with no flap, no
                             flip-back guard, no hold counter).

    night_deg / day_deg default to the module SUN_ALT_*_DEG constants,
    but callers pass the per-camera camera.json `state` override
    (sun_altitude_night_deg) so a single source of truth — the config —
    governs when night starts. The module constants remain the fallback
    when a camera.json omits the override.

    prev = {'mode': 'day'|'night', ...} (other fields ignored).
    Returns (mode, hold) where hold is just an incrementing tick
    counter — kept for state-file backwards compatibility; nothing
    reads it as a control input any more.

    If sun_alt_deg is None (location.json or ephem missing), default
    to day. This is the safe fall-back: a stuck day mode never starts
    the streaming daemon at all, no chance of writing pegged frames.
    """
    if night_deg is None:
        night_deg = SUN_ALT_NIGHT_DEG
    if day_deg is None:
        day_deg = SUN_ALT_DAY_DEG
    mode = prev.get("mode", "day")
    hold = int(prev.get("hold", 0)) + 1
    if sun_alt_deg is None:
        return "day", hold
    if sun_alt_deg < night_deg:
        return "night", hold
    if sun_alt_deg > day_deg:
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
    night_deg = night_threshold_deg()
    # v3w first: its mode gates whether v1 even bothers shooting.
    v3w_prev = state.get("v3w", {})
    v3w_mode, v3w_hold = decide_mode(v3w_prev, sun_alt_deg=sun_alt,
                                     night_deg=night_deg)
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
    v1_mode, v1_hold = decide_mode(v1_prev, sun_alt_deg=sun_alt,
                                   night_deg=night_deg)
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
