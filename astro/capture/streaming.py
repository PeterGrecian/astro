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
- Run() blocks until SIGTERM/SIGINT, the saturation guard fires (frame
  mean > saturation_full_scale_fraction × raw full scale), or the
  capture thread dies. Returning lets the per-tick mode controller take
  over with day capture instead; the return value says which happened
  ("signal" | "saturation" | "capture_failed").
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
    pedestal: int                          # CHART FLOOR (camera.json "pedestal")
    # The sensor's electronic zero (camera.json "black_level") — a physical
    # property, unlike `pedestal` which is an axis reference chosen for
    # footroom and is deliberately below the real floor. Kept separate because
    # conflating the two is what made a 2026-08 session read a fake chart floor
    # as a measurement. Stamped as BLACKLVL so downstream (accumulation, any
    # "ADU above zero" arithmetic) subtracts the physical value, never the
    # chart one. None = don't write the header.
    black_level: Optional[float] = None
    # Stage-1 inputs: brightness.csv lands at <frames_root>/YYYY/MM/DD/<camera>/.
    camera: str = ""                       # canonical camera name for brightness.csv path
    frames_root: Optional[Path] = None     # NFS root; if None, brightness.csv stays in buffer_dir
    mode: str = "night"                    # recorded per-row in brightness.csv
    # Camera/lens generation index (camera.json position_index). Stamped as
    # POSINDEX into every FITS so a frame self-identifies its calibration
    # epoch — the boundary across which plate scale / pole / FOV / pedestal
    # change and must NOT be mixed. None = don't write the header (cameras
    # that don't track position generations, e.g. eclipticam, stay unchanged).
    position_index: Optional[int] = None
    # Focus-dither experiment: step LensPosition per frame in a sawtooth
    # {"base": 3.15, "top": 5.15, "step": 0.10}. None = fixed lens_position
    # (normal capture). When set, each frame's commanded + reported focus is
    # written to the FITS header (LENSPOS / LENSPREP). Sweeps focus for
    # star-focus discovery + VCM mechanics + super-resolution radial dither.
    focus_dither: Optional[dict] = None
    # Sensor bit depth of a raw sample, independent of the uint16
    # container it arrives in. Full scale is (1 << sample_bits) - 1.
    sample_bits: int = 10
    # Raw alignment within the container. The Pi 5 (PiSP) unpacks 10-bit
    # raw into the TOP bits of the uint16 (every pixel a multiple of 64,
    # frame max 65472); the Pi 4 (VC6) unpacks into the bottom bits. None
    # = detect once from the first frame and latch; 0 = never shift. The
    # latched value is stamped into every FITS as RAWSHIFT so no
    # downstream reader has to infer alignment from pixel values.
    raw_shift: Optional[int] = None
    # Exit streaming when frame mean reaches this fraction of raw full
    # scale. Expressed as a fraction, not as "stops above pedestal",
    # because saturated raw means CANNOT exceed full scale — the old
    # "13 stops above pedestal" guard wanted mean >= 35.9M, unreachable,
    # so it never fired (night mode through full daylight on 2026-06-16,
    # 21 h of pegged frames). It is a fraction of SAMPLE full scale, not
    # of the uint16 ceiling: once raw_shift lands the data 10-bit, a
    # 0.95 x 65535 threshold is equally unreachable.
    saturation_full_scale_fraction: float = 0.95


def _detect_raw_shift(bayer, sample_bits: int) -> int:
    """How many bits the ISP left-shifted this raw frame, 0 if none.

    MSB-aligned raw is recognised by two facts together: it overflows
    sample full scale, and every pixel is a multiple of the shift. Both
    are needed — eclipticam's pre-2026-06-15 frames overflow too, but
    were *rescaled* by 65535/1023 = 64.06 rather than shifted, and must
    not be shifted. Run once per session, not per frame: a lens-capped
    or dead readout would fail a per-frame max test and silently emit
    one frame on the wrong scale inside an otherwise correct night.
    """
    full_scale = (1 << sample_bits) - 1
    if bayer.max() <= full_scale:
        return 0
    shift = 16 - sample_bits
    if np.all(bayer % (1 << shift) == 0):
        return shift
    return 0


def _capture_thread(cfg: StreamingConfig, picam2, q: queue.Queue,
                    stop: threading.Event,
                    log: logging.Logger, focus_dither: Optional[dict] = None):
    """Pull frames as fast as the camera will deliver; drop nothing
    here. Each item is (epoch_ms, bayer, lens_cmd, lens_rep, sensor_temp_c).

    focus_dither {"base","top","step"}: step LensPosition each frame in a
    sawtooth before capturing (settle briefly), and tag the frame with the
    commanded + reported focus. None = fixed focus (lens_cmd/lens_rep None)."""
    i = 0
    lp_cmd = lp_rep = temp_c = None
    if focus_dither:
        base = focus_dither["base"]; top = focus_dither["top"]
        step = focus_dither["step"]
        n = max(1, int(round((top - base) / step)))
    while not stop.is_set():
        if focus_dither:
            lp_cmd = round(base + (i % n) * step, 3)
            try:
                # AfMode 0 = Manual; re-assert each frame in case of glitch.
                picam2.set_controls({"AfMode": 0, "LensPosition": lp_cmd})
                time.sleep(0.3)   # VCM settle before the exposure
            except Exception as e:
                log.error(f"lens step failed: {e}")
        try:
            req = picam2.capture_request()
        except Exception as e:
            log.error(f"capture_request failed: {e}")
            time.sleep(1)
            continue
        try:
            bayer = req.make_array("raw").view(np.uint16).copy()
            # Hardware abstraction: Pi 5 (PiSP) MSB-aligns raw, Pi 4 (VC6)
            # LSB-aligns it. Decide once on the first frame and latch, so
            # every frame this session lands on one scale.
            if cfg.raw_shift is None:
                cfg.raw_shift = _detect_raw_shift(bayer, cfg.sample_bits)
                log.info(f"raw alignment: shift={cfg.raw_shift} bits "
                         f"(max={bayer.max()}, {cfg.sample_bits}-bit samples)")
            if cfg.raw_shift:
                bayer >>= cfg.raw_shift
            # One metadata fetch serves both the focus dither and the
            # thermal reading the nightly health gate needs.
            meta = req.get_metadata()
            if focus_dither:
                lp_rep = meta.get("LensPosition")
            temp_c = meta.get("SensorTemperature")
        finally:
            req.release()
        epoch_ms = int(time.time() * 1000)
        q.put((epoch_ms, bayer, lp_cmd, lp_rep, temp_c))
        i += 1


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
            epoch_ms, bayer, lp_cmd, lp_rep, temp_c = q.get(timeout=1.0)
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
        full_scale = float((1 << cfg.sample_bits) - 1)
        threshold = cfg.saturation_full_scale_fraction * full_scale
        if mean >= threshold:
            log.info(f"saturation: frame mean {mean:.0f} >= {threshold:.0f} "
                     f"({cfg.saturation_full_scale_fraction*100:.0f}% of "
                     f"{cfg.sample_bits}-bit full scale {full_scale:.0f}); exiting")
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
        # Self-describing raw alignment: how many bits were shifted off
        # the ISP's container to land these samples LSB-aligned. Archive
        # frames repacked after the fact carry the same keyword (see
        # bin/repack-msb); frames with neither are pre-2026-08 and must
        # be probed with max>full_scale and all(%64==0).
        h["RAWSHIFT"] = (cfg.raw_shift or 0,
                         "bits shifted off ISP-aligned raw")
        h["SAMPBITS"] = (cfg.sample_bits, "sensor raw sample depth")
        if temp_c is not None:
            # Direct reading, not a proxy. Dark current is NOT observable in
            # these frames — Sony's on-chip black-level correction references
            # optically-black pixels that share the thermal signal, so it is
            # subtracted before readout, and London sky-glow dominates what is
            # left. The thermal effect that does matter is focus drift, so the
            # nightly gate wants this alongside LENSPOS.
            h["SENSTEMP"] = (round(float(temp_c), 2), "sensor temperature, degC")
        if cfg.black_level is not None:
            h["BLACKLVL"] = (cfg.black_level,
                             "sensor electronic zero (NOT the chart pedestal)")
        if cfg.position_index is not None:
            h["POSINDEX"] = (cfg.position_index,
                             "camera/lens generation (camera.json position_index)")
        h["MEAN"] = mean
        h["PER_S"] = per_s
        if lp_cmd is not None:   # focus-dither run: record the per-frame focus
            h["LENSPOS"] = (lp_cmd, "commanded VCM dioptre (focus-dither)")
            h["LENSPREP"] = (float(lp_rep) if lp_rep is not None else -1.0,
                             "reported LensPosition (metadata)")
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
    capture_failed = False

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
                                 args=(cfg, cam, q, stop, log,
                                       cfg.focus_dither),
                                 daemon=True)
        comp_t = threading.Thread(target=_compress_thread,
                                  args=(cfg, q, stop, saturated, log),
                                  daemon=True)
        cap_t.start(); comp_t.start()
        log.info(f"streaming: cam={cfg.cam_idx} exp={cfg.exposure_us}us "
                 f"gain={cfg.gain} lp={cfg.lens_position} buf={cfg.buffer_dir} "
                 f"focus_dither={cfg.focus_dither}")
        while not stop.is_set():
            time.sleep(1.0)
            # A capture thread that dies (bad control, driver wedge, a
            # NameError in this file) used to leave run() sleeping here
            # forever: service "running", queue empty, zero frames, and
            # Restart=on-failure never triggered because nothing failed.
            if not cap_t.is_alive():
                log.error("capture thread died; ending the stream")
                capture_failed = True
                stop.set()
                break
        cap_t.join(timeout=5)
        comp_t.join(timeout=cfg.exposure_us / 1e6 + 10)
    finally:
        try:
            cam.stop(); cam.close()
        except Exception as e:
            log.warning(f"camera close: {e}")
    if capture_failed:
        return "capture_failed"
    return "saturation" if saturated.is_set() else "signal"
