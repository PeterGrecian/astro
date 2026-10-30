#!/usr/bin/env python3
"""Run plane_catch.Detector over a recorded MJPEG: clean, then with a synthetic plane."""
import sys, time
import numpy as np
sys.path.insert(0, ".")
from plane_catch import Detector, quarter
d = open(sys.argv[1], "rb").read()
parts = d.split(b"\xff\xd9\xff\xd8")
frames = [quarter(b"\xff\xd8" * (i > 0) + p + b"\xff\xd9" * (i < len(parts) - 1)) for i, p in enumerate(parts[:-1])]
print(len(frames), "frames", frames[0].shape, "sky", frames[0].mean().round(1), "frame-to-frame std", (frames[1] - frames[0]).std().round(2))
t = time.time(); det = Detector(); hits = [det.update(f) for f in frames]
dt = (time.time() - t) / len(frames)
t2 = time.time(); [quarter(b"\xff\xd8" + parts[1] + b"\xff\xd9") for _ in range(10)]; print(f"detect {dt * 1e3:.0f} ms, decode {(time.time() - t2) * 100:.0f} ms per frame")
print("clean: frames with hits", sum(bool(h) for h in hits), "scene changes", sum(h is None for h in hits))
for contrast, length, wid, label in ((-30, 24, 3, "dark 24x3"), (15, 24, 3, "bright 24x3"), (-8, 8, 2, "faint small 8x2"), (-30, 3, 2, "speck 3x2")):
    det = Detector(); caught = []
    for i, f in enumerate(frames):
        f = f.copy(); j = i - 30
        if 0 <= j < 40:
            x = 40 + j * 10; y = 100 + j * 2
            f[y:y + wid, x:x + length] += contrast
        h = det.update(f)
        if 0 <= j < 40 and h: caught.append(j)
    print(label, "caught", len(caught), "of 40")
