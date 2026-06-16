"""astro.capture.streaming — Picamera2 streaming capture loop.

Replaces the per-tick rpicam-still model (which leaves ~15 s dead per
60 s exposure and silently drops frames when rpicam-still hangs past
its subprocess timeout). Picamera2 is opened once at startup and held
for the whole night; capture_request() pulls back-to-back frames with
~100 ms readout between exposures (>99% duty cycle on IMX708 at 60 s).

Same pattern as starcam_night_daemon (Berrylands/gardencam) and
skycam_daemon_v2: capture thread writes raw Bayer .npy to a tmpfs
buffer dir and returns immediately. A compression worker thread in
the same process drains .npy, computes per-frame brightness, writes
.fits.fz, appends brightness.csv, deletes the .npy. An external
uploader service drains .fits.fz from tmpfs to NFS.

Caller responsibilities:
- Provide a StreamingConfig with sensor format, exposure, gain, and
  output dir paths (tmpfs and NFS).
- Run() blocks until SIGTERM/SIGINT or the brightness saturation guard
  fires (frame mean > saturation_pedestal_multiplier × pedestal).
  Returning lets the per-tick mode controller take over with day
  capture instead.
"""
from __future__ import annotations

import logging
import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import math

import numpy as np
from astropy.io import fits

from astro.brightness_log import BrightnessRow, append as append_brightness


@dataclass
class StreamingConfig:
    cam_idx: int
    sensor_size: tuple[int, int]           # (width, height) raw Bayer
    bayer_format: str                      # libcamera raw format e.g. "SRGGB10"
    bayer_pattern: str                     # FITS BAYERPAT e.g. "RGGB"
    exposure_us: int                       # per-frame integration
    gain: float
    lens_position: Optional[float]         # None = autofocus / no VCM
    rotation_180: bool                     # match rpicam-still --rotation 180
    camera_name: str                       # FITS CAMERA header
    buffer_dir: Path                       # tmpfs scratch for .fits.fz
    pedestal: int                          # sensor black level (camera.json)
    # Stage-1 inputs: brightness.csv lands at <frames_root>/YYYY/MM/DD/<camera>/.
    camera: str = ""                       # canonical camera name for brightness.csv path
    frames_root: Optional[Path] = None     # NFS root; if None, brightness.csv stays in buffer_dir
    mode: str = "night"                    # recorded per-row in brightness.csv
    # Exit streaming when frame mean reaches this fraction of the
    # uint16 container's max (65535). Expressed as a fraction, not as
    # "stops above pedestal", because saturated raw means CANNOT
    # exceed the dtype ceiling — the previous "13 stops above
    # pedestal" guard wanted mean >= 35.9M, unreachable in uint16, so
    # it never fired (stayed in night mode through full daylight on
    # 2026-06-16, 21 h of pegged frames).
    saturation_dtype_fraction: float = 0.95


def _capture_thread(picam2, q: queue.Queue, stop: threading.Event,
                    log: logging.Logger):
    """Pull frames as fast as the camera will deliver; drop nothing
    here. Each item is (epoch_ms, bayer_uint16_copy)."""
    while not stop.is_set():
        try:
            req = picam2.capture_request()
        except Exception as e:
            log.error(f"capture_request failed: {e}")
            time.sleep(1)
            continue
        try:
            bayer = req.make_array("raw").view(np.uint16).copy()
        finally:
            req.release()
        epoch_ms = int(time.time() * 1000)
        q.put((epoch_ms, bayer))


def _compress_thread(cfg: StreamingConfig, q: queue.Queue,
                     stop: threading.Event, saturated: threading.Event,
                     log: logging.Logger):
    """Pull (epoch_ms, bayer) off the queue, compute brightness,
    write Rice-compressed FITS, append brightness sidecar, delete
    the in-flight .npy (none yet — we go straight to .fits.fz here
    because the queue itself is the tmpfs buffer)."""
    cfg.buffer_dir.mkdir(parents=True, exist_ok=True)
    # Local sidecar in buffer dir kept for back-compat with uploader sweeps;
    # the canonical brightness.csv goes to NFS at <frames_root>/<night>/<cam>/.
    legacy_csv = cfg.buffer_dir / "brightness.csv"
    is_new_legacy = not legacy_csv.exists()
    legacy_fh = legacy_csv.open("a", buffering=1)
    if is_new_legacy:
        legacy_fh.write("epoch_ms,mean,exposure_us,gain,per_s\n")

    exposure_s = cfg.exposure_us / 1e6

    while not (stop.is_set() and q.empty()):
        try:
            epoch_ms, bayer = q.get(timeout=1.0)
        except queue.Empty:
            continue
        # Saturation guard: if the frame is bright enough to be daylight
        # we stop streaming and let the per-tick controller take over.
        mean = float(np.mean(bayer))
        per_s = mean / (exposure_s * cfg.gain) if exposure_s * cfg.gain else 0.0
        legacy_fh.write(f"{epoch_ms},{mean:.3f},{cfg.exposure_us},{cfg.gain},{per_s:.6e}\n")
        # Canonical brightness row for stage 1.
        if cfg.frames_root is not None and cfg.camera:
            stops = (math.log2(mean / cfg.pedestal)
                     if mean > 0 and cfg.pedestal > 0 else float("nan"))
            utc = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
            try:
                append_brightness(cfg.frames_root, cfg.camera, BrightnessRow(
                    utc_iso=utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    epoch_ms=epoch_ms,
                    mode=cfg.mode,
                    exptime_s=exposure_s,
                    gain=cfg.gain,
                    mean=mean,
                    per_s=per_s,
                    stops_above_pedestal=stops,
                ))
            except OSError as e:
                # NFS hiccup — keep capturing; stage 1 will fall back to
                # sun_altitude until brightness rows resume.
                log.warning(f"brightness.csv append failed: {e}")
        dtype_max = float(np.iinfo(bayer.dtype).max)
        threshold = cfg.saturation_dtype_fraction * dtype_max
        if mean >= threshold:
            log.info(f"saturation: frame mean {mean:.0f} >= {threshold:.0f} "
                     f"({cfg.saturation_dtype_fraction*100:.0f}% of "
                     f"{bayer.dtype} ceiling {dtype_max:.0f}); exiting")
            saturated.set()
            stop.set()
            break
        # Rotation matches rpicam-still --rotation 180 used elsewhere.
        if cfg.rotation_180:
            bayer = bayer[::-1, ::-1]
        out_path = cfg.buffer_dir / f"{epoch_ms}.fits.fz"
        tmp_path = cfg.buffer_dir / f"{epoch_ms}.fits.fz.tmp"
        hdu = fits.CompImageHDU(data=bayer, compression_type="RICE_1")
        h = hdu.header
        h["EXPTIME"] = cfg.exposure_us / 1e6
        h["GAIN"] = cfg.gain
        h["BAYERPAT"] = cfg.bayer_pattern
        h["DATE-OBS"] = datetime.fromtimestamp(epoch_ms/1000, tz=timezone.utc).isoformat()
        h["CAMERA"] = cfg.camera_name
        h["MEAN"] = mean
        h["PER_S"] = per_s
        fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(tmp_path, overwrite=True)
        tmp_path.rename(out_path)
    legacy_fh.close()


def run(cfg: StreamingConfig, log: Optional[logging.Logger] = None) -> str:
    """Open the camera, stream frames until SIGTERM or saturation.

    Returns one of: "signal" (stopped by SIGTERM/SIGINT) or
    "saturation" (frame brightness crossed daylight threshold).
    """
    if log is None:
        log = logging.getLogger("eclipticam-stream")
    # Lazy import: Picamera2 only exists on the Pi.
    from picamera2 import Picamera2

    cam = Picamera2(camera_num=cfg.cam_idx)
    cfgp = cam.create_video_configuration(
        raw={"size": cfg.sensor_size, "format": cfg.bayer_format},
        buffer_count=4,
    )
    cam.configure(cfgp)
    cam.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": cfg.gain,
        "FrameDurationLimits": (cfg.exposure_us, cfg.exposure_us),
        "ExposureTime": cfg.exposure_us,
    })
    if cfg.lens_position is not None:
        cam.set_controls({"AfMode": 0, "LensPosition": cfg.lens_position})

    stop = threading.Event()
    saturated = threading.Event()

    def _on_signal(signum, _frame):
        log.info(f"signal {signum}; stopping")
        stop.set()
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    q: queue.Queue = queue.Queue(maxsize=8)  # tmpfs back-pressure
    cam.start()
    try:
        # Drop first frame — controls may not be applied yet.
        req = cam.capture_request(); req.release()
        cap_t = threading.Thread(target=_capture_thread,
                                 args=(cam, q, stop, log), daemon=True)
        comp_t = threading.Thread(target=_compress_thread,
                                  args=(cfg, q, stop, saturated, log),
                                  daemon=True)
        cap_t.start(); comp_t.start()
        log.info(f"streaming: cam={cfg.cam_idx} exp={cfg.exposure_us}us "
                 f"gain={cfg.gain} lp={cfg.lens_position} buf={cfg.buffer_dir}")
        while not stop.is_set():
            time.sleep(1.0)
        cap_t.join(timeout=5)
        comp_t.join(timeout=cfg.exposure_us / 1e6 + 10)
    finally:
        try:
            cam.stop(); cam.close()
        except Exception as e:
            log.warning(f"camera close: {e}")
    return "saturation" if saturated.is_set() else "signal"
