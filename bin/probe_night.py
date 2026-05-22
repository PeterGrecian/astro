#!/usr/bin/env python3
"""Probe the camera in night-mode config and capture a few frames.

We learned that:
  * Bayer format is SGBRG10 (not SRGGB10 as the old daemon had)
  * Mode 3 = (2592, 1944), 15.6 fps max, exp max 3.07 s
  * create_still_configuration works (returns in 1.5 s with raw uint8)
  * create_video_configuration HANGS on first capture_request() — reason
    unknown yet

This script tries variants in sequence to isolate the hang.
"""
import sys
import time

import numpy as np
from picamera2 import Picamera2


def capture_n_via_still(cam: Picamera2, n: int = 4) -> None:
    print("=== still-configuration capture_array loop ===", flush=True)
    t0 = time.time()
    for i in range(n):
        arr = cam.capture_array("raw").view(np.uint16)
        dt = time.time() - t0
        print(f"  frame {i}: t={dt:.2f}s shape={arr.shape} "
              f"min={int(arr.min())} max={int(arr.max())} "
              f"mean={arr.mean():.1f}", flush=True)


def capture_n_via_request(cam: Picamera2, n: int = 4) -> None:
    print("=== capture_request loop (video config) ===", flush=True)
    t0 = time.time()
    for i in range(n):
        req = cam.capture_request()
        try:
            arr = req.make_array("raw").view(np.uint16)
            md = req.get_metadata()
            dt = time.time() - t0
            print(f"  frame {i}: t={dt:.2f}s shape={arr.shape} "
                  f"min={int(arr.min())} max={int(arr.max())} "
                  f"mean={arr.mean():.1f} "
                  f"exp={md.get('ExposureTime',0)/1e6:.2f}s", flush=True)
        finally:
            req.release()


def main() -> int:
    INTERVAL_US = 3_000_000
    EXP_US = 2_000_000
    MODE = sys.argv[1] if len(sys.argv) > 1 else "still"

    cam = Picamera2()

    if MODE == "still":
        print("config: create_still_configuration full-frame raw", flush=True)
        cfg = cam.create_still_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=2,
        )
        cam.configure(cfg)
        cam.set_controls({"ExposureTime": EXP_US, "AnalogueGain": 16.0,
                          "AeEnable": False, "AwbEnable": False})
        cam.start()
        time.sleep(1)
        capture_n_via_still(cam, 4)
        cam.stop()
        return 0

    if MODE == "still-req":
        print("config: create_still_configuration + capture_request loop",
              flush=True)
        cfg = cam.create_still_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=2,
        )
        cam.configure(cfg)
        cam.set_controls({"ExposureTime": EXP_US, "AnalogueGain": 16.0,
                          "AeEnable": False, "AwbEnable": False})
        cam.start()
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    if MODE == "video":
        print("config: create_video_configuration full-frame", flush=True)
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=4,
            controls={
                "FrameDurationLimits": (INTERVAL_US, INTERVAL_US),
                "ExposureTime": EXP_US,
                "AnalogueGain": 16.0,
                "AeEnable": False,
                "AwbEnable": False,
            },
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    if MODE == "video-no-fdl":
        print("config: create_video_configuration full-frame, NO FrameDurationLimits",
              flush=True)
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=4,
            controls={
                "ExposureTime": EXP_US,
                "AnalogueGain": 16.0,
                "AeEnable": False,
                "AwbEnable": False,
            },
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    if MODE == "video-setcontrols":
        print("config: video, no controls in cfg, set_controls after", flush=True)
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=4,
        )
        cam.configure(cfg)
        cam.set_controls({
            "ExposureTime": EXP_US,
            "AnalogueGain": 16.0,
            "AeEnable": False,
            "AwbEnable": False,
        })
        cam.start()
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    if MODE == "video-live-fdl":
        print("config: video bare, set FDL+exp LIVE after start", flush=True)
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=4,
        )
        cam.configure(cfg)
        cam.start()
        # Apply controls after start.
        cam.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "AnalogueGain": 16.0,
            "FrameDurationLimits": (INTERVAL_US, INTERVAL_US),
            "ExposureTime": EXP_US,
        })
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    if MODE == "video-fdl-loose":
        print("config: video, FrameDurationLimits=(64ms..3.07s) wide range",
              flush=True)
        # The sensor's native FrameDurationLimits range is
        # (63965, 3067365). Set the WHOLE range, so the camera can pick
        # the exposure-driven duration freely.
        cfg = cam.create_video_configuration(
            raw={"size": (2592, 1944), "format": "SGBRG10"},
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=4,
            controls={
                "FrameDurationLimits": (63965, 3067365),
                "ExposureTime": EXP_US,
                "AnalogueGain": 16.0,
                "AeEnable": False,
                "AwbEnable": False,
            },
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1)
        capture_n_via_request(cam, 4)
        cam.stop()
        return 0

    print(f"unknown mode: {MODE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
