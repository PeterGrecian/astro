#!/usr/bin/env python3
"""Fixed and per-frame banding in fshq frames, ignoring the ends of each line profile."""
import numpy as np
from astropy.io import fits

D = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30/18"
def load(n):
    with fits.open(f"{D}/20261030T174011Z-{n:05d}.fits.fz") as h:
        return h[1].data.astype(np.float32)
frames = np.array([load(n) for n in range(1001, 1041)])
med = np.median(frames, axis=0)
for name, ax in (("rows", 2), ("columns", 1)):
    mean_lines = frames.mean(axis=ax)
    m = mean_lines.mean(axis=0)
    t = m - np.convolve(m, np.ones(51) / 51, "same")
    t = t[60:-60]
    print(f"{name}: fixed banding {t.std():.3f} ADU (range {t.min():.2f}..{t.max():.2f}), per-frame {(mean_lines - m)[:, 60:-60].std():.3f} ADU")
    f = np.abs(np.fft.rfft(t - t.mean()))
    k = np.argsort(-f[2:])[:4] + 2
    print("   strongest periods (lines):", [round(len(t) / int(i), 1) for i in k])
    sm = np.abs(np.fft.rfft(mean_lines[0][60:-60] - m[60:-60]))
    k = np.argsort(-sm[2:])[:4] + 2
    print("   per-frame strongest periods:", [round(len(t) / int(i), 1) for i in k])
print("fixed pattern per pixel, median of 40 frames: std", round(float(np.std(med[(med > 240) & (med < 285)])), 2))
print("one frame: pixel std", round(float(np.std(frames[0][(frames[0] > 240) & (frames[0] < 285)])), 2), " after removing the 40-frame median:", round(float(np.std((frames[0] - med)[np.abs(frames[0] - med) < 25])), 2))
print("90% display range of one frame (what a 0.5..99.5 stretch shows):", np.percentile(frames[0][::5, ::5], [0.5, 99.5]))

n = frames[0].shape
for name, ax, count in (("rows", 2, n[1]), ("columns", 1, n[0])):
    lines = (frames - med).mean(axis=ax)
    print(f"{name}: per-frame line noise {lines[:, 60:-60].std():.3f} ADU, pure pixel noise would give {1.55 / count ** .5:.3f}")
