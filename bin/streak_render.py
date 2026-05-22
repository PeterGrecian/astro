#!/usr/bin/env python3
"""Streak accumulator across the last N frames.

Pass-1 design: for each consecutive frame pair (F_{n-1}, F_n):
    A_abs += |F_n - F_{n-1}|

Every pixel a star transits gets bright. Static background cancels.
"""
import glob, os, sys, time
import numpy as np
import cv2

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
print(f"available: {len(files)} frames")
# Skip newest 2 (might be mid-write or just-just-written)
files = files[:-2][-N:]
print(f"using last {len(files)} (span: {time.strftime('%H:%M:%S', time.gmtime(os.path.getmtime(files[0])))} → "
      f"{time.strftime('%H:%M:%S UTC', time.gmtime(os.path.getmtime(files[-1])))})")

if len(files) < 2:
    print("not enough frames", file=sys.stderr); sys.exit(1)

a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = np.load(files[0]).astype(np.int32)
peak = 0
for i, fn in enumerate(files[1:], 1):
    cur = np.load(fn).astype(np.int32)
    diff = np.abs(cur - prev)
    a_abs += diff
    prev = cur
    if i % 50 == 0:
        print(f"  ...{i}/{len(files)-1} frames accumulated, peak so far: {int(a_abs.max())}")
print(f"a_abs: min={int(a_abs.min())} max={int(a_abs.max())} mean={a_abs.mean():.1f}")

# Demosaic the accumulator treating as monochrome.
# Take 8-bit for visualisation.
p_lo = np.percentile(a_abs, 50)
p_hi = np.percentile(a_abs, 99.9)
print(f"stretch: {p_lo:.1f} .. {p_hi:.1f}")

stretched = np.clip((a_abs.astype(np.float32) - p_lo) * 255.0 / max(1, p_hi - p_lo),
                    0, 255).astype(np.uint8)

# Bayer interpretation: skip the demosaic to avoid colour artefacts.
# Save as grayscale.
out = "/tmp/streak.jpg"
cv2.imwrite(out, stretched, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(f"wrote {out}")
print(f"size: {os.path.getsize(out) // 1024} KB")
