#!/usr/bin/env python3
"""Defocus between two live-view frames of one scene: blur the sharp one with an
annular pupil of diameter b until it matches the other.

    scenedefocus.py SHARP FRAME [--scale 3.13]

Uses the whole scene, allowing a shift and a brightness change. Frames are
approximately linearised (gamma 2.2). The sign of the defocus is not measured.
"""
import argparse
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve

F, N, PITCH = 300.0, 4.0, 1.55e-3
OBS = 0.33    # central obstruction, assumed
ROWS = 972    # stream rows above the burned-in readout


def load(path):
    g = np.asarray(Image.open(path).convert("RGB")).astype(float)[:ROWS, :, 1]
    return (g / 255) ** 2.2


def pupil(b):
    r = int(b // 2) + 1
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    rr = np.hypot(xx, yy)
    k = ((rr <= b / 2) & (rr >= OBS * b / 2)).astype(float)
    return k / k.sum()


def score(sharp, frame, b, m=170):
    blurred = fftconvolve(sharp, pupil(b), mode="same") if b >= 2 else sharp
    a = blurred[m:-m, m:-m]
    best = (9e9, 0, 0, 0, 0)
    for dy in range(-40, 41, 4):
        for dx in range(-40, 41, 4):
            t = frame[m + dy:ROWS - m + dy, m + dx:frame.shape[1] - m + dx]
            A = np.vstack([a.ravel(), np.ones(a.size)]).T
            c, *_ = np.linalg.lstsq(A[::9], t.ravel()[::9], rcond=None)
            rms = np.sqrt(np.mean((c[0] * a + c[1] - t) ** 2))
            if rms < best[0]:
                best = (rms, dx, dy, c[0], c[1])
    return best


ap = argparse.ArgumentParser()
ap.add_argument("sharp")
ap.add_argument("frame")
ap.add_argument("--scale", type=float, default=4056 / 1296)
args = ap.parse_args()
sharp, frame = load(args.sharp), load(args.frame)
res = {}
for b in [0, 20, 40, 60, 80, 100, 110, 120, 130, 140, 150, 160, 170, 180, 200, 230, 260, 300]:
    res[b] = score(sharp, frame, b)
    r = res[b]
    print(f"b {b:4d}  rms {r[0]:.5f}  shift ({r[1]:+d},{r[2]:+d})  gain {r[3]:.2f}  mm {b * args.scale * PITCH * N:.2f}")
b = min(res, key=lambda k: res[k][0])
print(f"best b {b} px -> defocus {b * args.scale * PITCH * N:.2f} mm")
