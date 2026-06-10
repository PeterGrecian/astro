#!/usr/bin/env python3
"""Force one day-mode tick on both eclipticam cameras (JPG).

Reuses capture.py's helpers so the on-disk layout matches the production
pipeline:  day/<utc-date>/<cam>/HH/NNNN.jpg
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture as c

now = datetime.now(timezone.utc)
utc_date = now.strftime("%Y-%m-%d")
hh = now.strftime("%H")
for cam_label, cam_idx, lp in [("v3w", c.CAM_V3W, c.LENS_POSITION_V3W),
                                ("v1",  c.CAM_V1,  None)]:
    hour_dir = c.FRAMES / "day" / utc_date / cam_label / hh
    out = c.next_frame_path(hour_dir, "jpg")
    c.shoot_day(cam_idx, out, lens_position=lp)
    print(f"{now:%H:%M:%S}Z {cam_label} -> {out}", flush=True)
