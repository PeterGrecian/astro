#!/usr/bin/env python3
"""astrocam-v3-night — long-running streaming capture for astrocam's imx708.

Commissioned 2026-07-29 when the imx219 (Camera Module v2) was replaced by
a standard Camera Module v3 (imx708). Mirrors eclipticam's
v3w_night_daemon.py: a thin wrapper over the shared astro.capture.streaming
engine, with astrocam's sensor/lens/exposure values pulled from
astrocam/camera.json's `capture` block.

Started by systemd when astrocam flips to night mode; exits when:
  - SIGTERM (flipped back to day) -> exit 0
  - frame mean crosses the dawn saturation threshold -> exit 0
  - camera error -> exit non-zero (systemd Restart=on-failure)

Writes Rice-compressed FITS to a tmpfs buffer; an uploader drains it to NFS.

NB: the pole_prior, plate_scale, pedestal and occlusion tile map in
camera.json are all STALE (imx219/v2-lens/3280x2464 era) and must be
re-derived from real imx708 sky frames before the astrometry is valid.
"""
import logging
import os
import sys
from pathlib import Path

# Allow running directly or via systemd ExecStart with the repo on
# PYTHONPATH; either way, find astro.capture.
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.capture.streaming import StreamingConfig, run
from astro.config import CameraConfig

CAM_IDX = 0
# Canonical camera name for stage-1 brightness.csv path. Distinct from
# camera_name (the FITS CAMERA header / sensor model).
CAMERA = "astrocam"
BUFFER_DIR = Path(os.environ.get("ASTROCAM_BUFFER_DIR",
                                 "/var/lib/astrocam-buffer/v3"))


def _param(env, cfg_val, fallback, cast):
    """Resolve a capture param: env var override -> camera.json -> fallback.
    Single source of truth is camera.json's `capture` block; env vars stay
    as a per-host escape hatch (e.g. a cold-night lens position)."""
    raw = os.environ.get(env)
    if raw is not None:
        return cast(raw)
    if cfg_val is not None:
        return cast(cfg_val)
    return cast(fallback)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg_cam = CameraConfig.load("astrocam")
    cap = cfg_cam.get("capture") or {}
    frames_root = cfg_cam.frames_root
    # Camera/lens generation index -> stamped as POSINDEX in every FITS so
    # each frame self-identifies its calibration epoch (imx219/v2=1,
    # imx708/v3s=2). See camera.json position_registry.
    position_index = cfg_cam.get("position_index")

    exposure_us = _param("ASTROCAM_EXPOSURE_US", cap.get("night_exposure_us"),
                         59_900_000, int)
    gain = _param("ASTROCAM_GAIN", cap.get("night_gain"), 1.0, float)
    lens_position = _param("ASTROCAM_LENS_POSITION", cap.get("lens_position"),
                           1.0, float)
    pedestal = _param("ASTROCAM_PEDESTAL", cfg_cam.get("pedestal"), 512, int)

    # Focus dither: on by default from camera.json's capture.focus_dither
    # (probed lp=1.0 +/- 0.5, step 0.1). Set ASTROCAM_FOCUS_DITHER=0 to
    # pin the single lens_position instead. Overridable ranges via
    # ASTROCAM_FD_BASE/TOP/STEP.
    focus_dither = cap.get("focus_dither")
    if os.environ.get("ASTROCAM_FOCUS_DITHER") == "0":
        focus_dither = None
    elif focus_dither is not None or os.environ.get("ASTROCAM_FOCUS_DITHER") == "1":
        base = float(os.environ.get("ASTROCAM_FD_BASE",
                                    (focus_dither or {}).get("base", 0.5)))
        top = float(os.environ.get("ASTROCAM_FD_TOP",
                                   (focus_dither or {}).get("top", 1.5)))
        step = float(os.environ.get("ASTROCAM_FD_STEP",
                                    (focus_dither or {}).get("step", 0.1)))
        focus_dither = {"base": base, "top": top, "step": step}

    logging.info(f"capture params: exposure_us={exposure_us} gain={gain} "
                 f"lens_position={lens_position} pedestal={pedestal} "
                 f"focus_dither={focus_dither} position_index={position_index}")

    cfg = StreamingConfig(
        cam_idx=CAM_IDX,
        # imx708 native full-res raw Bayer. Same choice as eclipticam-v3w.
        sensor_size=(4608, 2592),
        bayer_format="SRGGB10",
        bayer_pattern="RGGB",
        exposure_us=exposure_us,
        gain=gain,
        lens_position=lens_position,
        # astrocam mounts the sensor inverted (camera.json rotate_180);
        # match rpicam-still --rotation 180 used for the day/test frames.
        rotation_180=True,
        camera_name="imx708",
        buffer_dir=BUFFER_DIR,
        pedestal=pedestal,
        camera=CAMERA,
        frames_root=frames_root,
        mode="night",
        focus_dither=focus_dither,
        position_index=position_index,
    )
    reason = run(cfg)
    logging.info(f"exiting cleanly (reason={reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
