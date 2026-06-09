#!/usr/bin/env python3
"""eclipticam capture: every-10-min sun/moon imaging, shoot-only.

Captures v3w (camera 0, fixed lens-position 0.0) and v1 (camera 1) and
writes JPEGs into the NFS-mounted layout

    ~/eclipticam-frames/series/YYYY-MM-DD/<camera>/HHMM.jpg

No CSV, no detection, no annotation. Downstream tools on pip will read
the frame tree and do their own analysis.
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
FRAMES = HOME / "eclipticam-frames" / "series"
LENS_POSITION_V3W = 0.0  # true infinity for sky targets

CAM_V3W = 0
CAM_V1 = 1


def shoot(camera_idx, out_path, lens_position=None, timeout_ms=1500):
    cmd = [
        "rpicam-still",
        "--camera", str(camera_idx),
        "--rotation", "180",
        "-o", str(out_path),
        "-n",
        "-t", str(timeout_ms),
    ]
    if lens_position is not None:
        cmd += ["--autofocus-mode", "manual", "--lens-position", str(lens_position)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not out_path.exists():
        print(f"capture FAILED cam{camera_idx} -> {out_path}", file=sys.stderr)
        print(r.stderr[-400:], file=sys.stderr)


def capture_tick():
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H%M")
    for cam_label, cam_idx, lp in [("v3w", CAM_V3W, LENS_POSITION_V3W),
                                    ("v1", CAM_V1, None)]:
        out_dir = FRAMES / day / cam_label
        out_dir.mkdir(parents=True, exist_ok=True)
        shoot(cam_idx, out_dir / f"{hhmm}.jpg", lens_position=lp)


if __name__ == "__main__":
    capture_tick()
