#!/usr/bin/env python3
"""Defocus of the FirstScope from the blur of a known ball in a live-view frame.

    balldefocus.py FRAME [--xy X Y] [--diam 131] [--scale 3.13]

Azimuthal median profile about the ball, fitted with disc(ball) convolved with
an annular pupil. Blur diameter b (stream px) -> defocus = b * scale * pitch * N.
Sign is not measured: blur is the same on both sides of focus.
"""
import argparse
import numpy as np
from PIL import Image

F, N, PITCH, BALL = 300.0, 4.0, 1.55e-3, 67.0
OBS = 0.33    # central obstruction, assumed
BAND = 972    # stream rows above the burned-in readout


def profile(g, cx, cy, rmax=260):
    h, w = g.shape
    yy, xx = np.mgrid[:h, :w]
    r = np.hypot(xx - cx, yy - cy).astype(int)
    return np.array([np.median(g[r == i]) if (r == i).any() else np.nan for i in range(rmax)])


def model(R, b, rmax=260, n=2048):
    """Radial profile of disc(R) convolved with an annular pupil of diameter b."""
    yy, xx = np.mgrid[-n // 2:n // 2, -n // 2:n // 2]
    rr = np.hypot(xx, yy)
    disc = rr <= R
    if b < 2:
        im = disc.astype(float)
    else:
        pupil = (rr <= b / 2) & (rr >= OBS * b / 2)
        im = np.fft.irfft2(np.fft.rfft2(disc) * np.fft.rfft2(np.fft.ifftshift(pupil))) / pupil.sum()
    return im[n // 2, n // 2:n // 2 + rmax]


def fit(prof, R0):
    r = np.arange(len(prof))
    ok = np.isfinite(prof)
    best = None
    for b in [0, 10, 20, 40, 60, 80, 100, 120, 140, 160, 180, 220]:
        m = model(R0, b, len(prof))
        A = np.vstack([m[ok], np.ones(ok.sum())]).T
        c, *_ = np.linalg.lstsq(A, prof[ok], rcond=None)
        rms = np.sqrt(np.mean((A @ c - prof[ok]) ** 2))
        print(f"  b {b:4d} px  rms {rms:6.2f}  contrast {c[0]:6.1f}  bg {c[1]:6.1f}")
        if best is None or rms < best[0]:
            best = (rms, b, c)
    return best


ap = argparse.ArgumentParser()
ap.add_argument("frame")
ap.add_argument("--xy", nargs=2, type=int, default=[766, 384], help="ball centre, stream px")
ap.add_argument("--diam", type=float, default=131.0, help="sharp ball width, stream px (probed)")
ap.add_argument("--scale", type=float, default=4056 / 1296)
a = ap.parse_args()
g = np.asarray(Image.open(a.frame).convert("RGB")).astype(float)[:BAND, :, 1]
cx, cy = a.xy
R0 = a.diam / 2
dist = F * (1 + BALL / (a.diam * a.scale * PITCH))
prof = profile(g, cx, cy)
print(f"{a.frame}\ncentre ({cx:.0f},{cy:.0f}); ball {2 * R0:.0f} px, so {dist / 1e3:.1f} m")
print("profile every 20 px:", np.round(prof[::20]).astype(int).tolist())
rms, b, c = fit(prof, R0)
d = b * a.scale * PITCH * N
want = F ** 2 / (dist - F)
print(f"best blur {b} px -> defocus {d:.2f} mm; infinity needs {want:.2f} mm from focus on the ball "
      f"(blur {want / N / PITCH / a.scale:.0f} px)")
