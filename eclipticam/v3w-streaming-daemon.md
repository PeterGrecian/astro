# v3w streaming night capture daemon — design sketch

**Status**: not deployed. Returning to this after the per-tile derot work is done.

## Why

Current v3w night capture uses `rpicam-still` per systemd-timer tick. Measured behaviour on 2026-06-12 night: 55 s exposure but ~70 s start-to-start interval — **~15 s dead time per cycle** from libcamera startup, sensor settle, file write, and timer overhead. Each star trail in a 10-min max-stack therefore appears as a dotted line (55 s bright, 15 s dark, 55 s bright, …) rather than a continuous streak.

The v1 night code (`shoot_night_v1_stack` in `capture.py`) already proved the right pattern works on eclipticam: `Picamera2` opened once, frames pulled via `capture_request()` back-to-back. On v1 we saw 3 s exposures with ~60 ms readout — practically always-open shutter, no jitter.

For v3w at 55 s exposure, IMX708 readout is similar (~100 ms), so streaming gives **>99.8% duty cycle**. Continuous trails for fitting, more honest brightness samples, no astronomical dead time.

## Architecture

- **One long-running process per night**, replacing the per-minute systemd-timer fires.
- Process opens `Picamera2(camera_num=CAM_V3W)` once at startup.
- Inner loop: `capture_request()` → write FITS → update brightness state → decide if mode should change.
- Exits cleanly when brightness state machine flips to day; existing per-tick `capture.py` day path (rpicam-still snapshots) takes over.
- Mode changes that need format reconfigure (day ⟷ night, FITS vs JPG) tear the camera down + start; mode changes that only need exposure adjustment (within night, e.g. brightening sky) use `cam.set_controls({"ExposureTime": …})` in-flight.

## Sketch (not committed as runnable code)

```python
#!/usr/bin/env python3
"""eclipticam-v3w-night — long-running v3w night capture daemon.

Holds Picamera2 open continuously across night. Streaming frames are
read back via capture_request() with near-zero dead time between
exposures (60-100 ms readout out of 55s ≈ 99.9% duty cycle).

State machine still runs (decide_mode), but in-process — not via
systemd timer ticks. systemd starts ONE process per night, this
process owns the camera.

Day mode: process exits cleanly so the existing day-only path
(per-tick rpicam-still via the original capture.py) takes over.
Night mode: streaming loop runs until brightness pushes us back to day.
"""
import json, signal, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits
from picamera2 import Picamera2

CAM_V3W = 0
FRAMES = Path.home() / "eclipticam-frames"
STATE_FILE = Path("/var/lib/eclipticam/luminance.json")
LENS_POSITION = 0.0
NIGHT_EXPOSURE_US = 55_000_000
NIGHT_GAIN = 1.0
SHUTDOWN_REQUESTED = False


def signal_handler(signum, frame):
    global SHUTDOWN_REQUESTED
    SHUTDOWN_REQUESTED = True


def night_date_for(utc_dt):
    """Noon-rollover: night-of date = (utc - 12h).date()."""
    return (utc_dt - timedelta(hours=12)).strftime("%Y-%m-%d")


def next_frame_path(hour_dir):
    """Per-hour zero-padded counter — same convention as the current
    capture.py."""
    hour_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(hour_dir.glob("*.fits.fz"))
    n = int(existing[-1].stem) + 1 if existing else 1
    return hour_dir / f"{n:04d}.fits.fz"


def write_fits(out_path, data, exposure_us, gain, utc_obs):
    """Same FITS format as the original capture.py shoot_night_one
    output so existing downstream code reads it transparently."""
    hdu = fits.CompImageHDU(data=data, compression_type="RICE_1")
    hdu.header["EXPTIME"] = exposure_us / 1e6
    hdu.header["GAIN"] = gain
    hdu.header["DATE-OBS"] = utc_obs.isoformat()
    hdu.header["BAYERPAT"] = "RGGB"   # IMX708 wide raw pattern
    hdu.header["INSTRUME"] = "IMX708 Wide"
    hdu.header["TELESCOP"] = "eclipticam"
    hdu.header["ROWORDER"] = "TOP-DOWN"
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(out_path, overwrite=True)


def update_brightness_state(mean_pixel, exposure_us, gain):
    """Read state, update lum metric, write back. Identical metric to
    the existing capture.py: mean / (exposure_us * gain). The lum
    decides if we exit and let the day path take over."""
    lum = float(mean_pixel) / (exposure_us * gain) if exposure_us * gain > 0 else None
    try:
        state = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        state = {}
    v3w = state.get("v3w", {})
    v3w["mode"] = "night"
    v3w["lum"] = lum
    v3w["hold"] = v3w.get("hold", 0) + 1
    state["v3w"] = v3w
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))
    return lum


def should_exit_to_day(lum):
    """Borrowed from existing capture.py decide_mode logic, simplified.
    Saturated daytime frame returns lum >= SATURATED_EXIT (1.0); plain
    too-bright also triggers exit. Mode-hold ticks already lapsed by
    the time this daemon starts (it's already in night)."""
    LUMINANCE_NIGHT_EXIT = 0.005
    SATURATED_EXIT = 0.5
    return lum is not None and (lum >= SATURATED_EXIT or lum > LUMINANCE_NIGHT_EXIT)


def run():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"[{datetime.now()}] eclipticam-v3w-night: starting Picamera2")
    cam = Picamera2(camera_num=CAM_V3W)
    config = cam.create_video_configuration(
        # Raw Bayer at full resolution; main stream is small + unused.
        raw={"size": (4608, 2592), "format": "SBGGR10"},  # check actual pattern
        controls={
            "ExposureTime": NIGHT_EXPOSURE_US,
            "AnalogueGain": NIGHT_GAIN,
            "AeEnable": False,            # manual exposure, no AE meddling
            "AwbEnable": False,           # no white-balance (raw)
            "LensPosition": LENS_POSITION,
            "AfMode": 0,                  # manual focus
            "FrameDurationLimits": (NIGHT_EXPOSURE_US, NIGHT_EXPOSURE_US),
        },
    )
    cam.configure(config)
    cam.start()
    # Settle: discard first 2 frames so AE-equivalent stabilises (even
    # with AE off, gain switches in the IPA take a frame or two).
    for _ in range(2):
        req = cam.capture_request()
        req.release()
    print(f"[{datetime.now()}] streaming at {NIGHT_EXPOSURE_US/1e6}s exposure")

    n_captured = 0
    try:
        while not SHUTDOWN_REQUESTED:
            req = cam.capture_request()
            # Wall-clock timestamp at request return = end of exposure.
            # Subtract exposure_us to get the start, which is what
            # DATE-OBS should record (consistent with the original).
            t_end = datetime.now(timezone.utc)
            t_start = t_end - timedelta(microseconds=NIGHT_EXPOSURE_US)
            raw = req.make_array("raw")   # numpy ndarray of the Bayer
            req.release()

            # Write synchronously — at 55s exposure we have plenty of
            # time before the next frame is ready.
            night_date = night_date_for(t_start)
            hh = t_start.strftime("%H")
            hour_dir = FRAMES / "night" / night_date / "v3w" / hh
            out_path = next_frame_path(hour_dir)
            write_fits(out_path, raw, NIGHT_EXPOSURE_US, NIGHT_GAIN, t_start)
            n_captured += 1

            # Brightness state update + mode check.
            mean = float(np.mean(raw))
            lum = update_brightness_state(mean, NIGHT_EXPOSURE_US, NIGHT_GAIN)
            if should_exit_to_day(lum):
                print(f"[{datetime.now()}] brightness up (lum={lum:.6f}); "
                      f"exiting after {n_captured} frames")
                break

            if n_captured % 10 == 0:
                print(f"[{datetime.now()}] wrote {out_path}  "
                      f"mean={mean:.0f}  lum={lum:.6f}")

    finally:
        print(f"[{datetime.now()}] stopping camera, captured {n_captured}")
        cam.stop()
        cam.close()
        # Update state so the per-tick day-only path picks up "I'm day now"
        try:
            state = json.loads(STATE_FILE.read_text())
        except (OSError, ValueError):
            state = {}
        v3w = state.get("v3w", {})
        v3w["mode"] = "day"
        v3w["hold"] = 0
        state["v3w"] = v3w
        STATE_FILE.write_text(json.dumps(state))


if __name__ == "__main__":
    run()
```

## Things to think about before this lands

1. **systemd unit shape** — `Type=simple` with `Restart=on-failure`, started by a timer that fires only at dusk. Or: started always; daemon's first action is to check if we should be in night mode and exit if not. The latter is more robust to restarts.

2. **Handover to day mode** — when the daemon exits, the existing minute-tick `capture.py` day path (rpicam-still) takes over. State-file write at exit is the handshake.

3. **Frame timing in `DATE-OBS`** — original capture wrote the moment `rpicam-still` finished (effectively post-readout time, not shutter open). Streaming version records `t_end - exposure_us` — more accurate.

4. **Format pin** — `"SBGGR10"` in raw config is a guess. v3w's IMX708 native pattern needs confirming; might be `"SRGGB10"`. `rpicam-still --list-cameras` will tell us; not a code question.

5. **Disk write blocking** — at 55s/frame we have ~55s to write the previous frame before the next is ready. Plenty of headroom for synchronous I/O. No threadpool needed.

6. **Cover servo** — not touched here. If cover lives in the same systemd unit's `ExecStartPre`/`ExecStopPost`, fine; otherwise this daemon assumes cover is already open when started.

7. **Bad-frame detection** — guard against `make_array("raw")` returning garbage (sensor reset, dropped frame). Sanity check `raw.mean() > 0 and raw.mean() < 65000` before writing.

## Open question: AE

Decision: **no libcamera AE** (`AeEnable: False`). The existing brightness state machine in `capture.py` is our AE-equivalent — it picks exposure mode based on scene mean, which is more predictable than libcamera's IPA for our specific sky / cover / light pollution. The state machine signals mode changes; the streaming loop reacts with `set_controls()` for in-mode adjustment and `cam.stop()`+`configure()`+`start()` for full mode transitions.

## Related work

- `astro/eclipticam/capture.py` — existing per-tick capture, kept for day mode and for v1 (where the 10-min cadence makes streaming unnecessary).
- `shoot_night_v1_stack` in same file — already uses Picamera2 streaming, but only within one tick and only for v1 (3 s frames coadded). Pattern is the model for v3w streaming.
