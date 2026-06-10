#!/usr/bin/env python3
"""Try to unstick the v3w VCM: slam between extremes, then park at lp=0
and capture a still. Repeat N cycles to see if the result is bimodal.

Outputs jpgs under day/<utc-date>/v3w/<HH>/ alongside the regular day
captures.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture as c

from picamera2 import Picamera2
from libcamera import controls

LP_LO = 0.0
LP_HI = 15.0   # libcamera dioptre range top end for IMX708
SLAM_CYCLES = 10
SETTLE_S = 0.15
N_RUNS = 5


def cycle_and_park(cam, lp):
    # Slam phase: alternate extremes as fast as we can.
    for _ in range(SLAM_CYCLES):
        cam.set_controls({"LensPosition": LP_HI})
        cam.set_controls({"LensPosition": LP_LO})
    # Settle phase: command lp=lp and give VCM time to actually arrive.
    cam.set_controls({"LensPosition": lp})
    time.sleep(SETTLE_S * 4)


def main():
    cam = Picamera2(camera_num=c.CAM_V3W)
    still = cam.create_still_configuration(main={"size": (2304, 1296)})
    cam.configure(still)
    cam.set_controls({"AfMode": controls.AfModeEnum.Manual})
    cam.start()
    time.sleep(0.3)

    now = datetime.now(timezone.utc)
    utc_date = now.strftime("%Y-%m-%d")
    hh = now.strftime("%H")
    hour_dir = c.FRAMES / "day" / utc_date / "v3w" / hh
    hour_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, N_RUNS + 1):
        cycle_and_park(cam, LP_LO)
        out = c.next_frame_path(hour_dir, "jpg")
        cam.capture_file(str(out))
        print(f"run {i}/{N_RUNS} lp={LP_LO} -> {out}", flush=True)

    cam.stop()
    cam.close()


if __name__ == "__main__":
    main()
