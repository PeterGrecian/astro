#!/usr/bin/env python3
"""Render the latest stable night frame as a viewable JPG.

- pick the 2nd-most-recent .npy (avoid mid-write)
- demosaic SGBRG10 Bayer to RGB
- stretch the dynamic range (linear, percentile clip)
- save JPG + a stats line
"""
import glob, os, sys, time
import numpy as np
import cv2

files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
if len(files) < 2:
    print("no frames", file=sys.stderr); sys.exit(1)
target = files[-2]
print(f"src: {target}")
print(f"mtime: {time.strftime('%H:%M:%S UTC', time.gmtime(os.path.getmtime(target)))}")

bayer = np.load(target)
print(f"raw: shape={bayer.shape} dtype={bayer.dtype} "
      f"min={int(bayer.min())} max={int(bayer.max())} "
      f"mean={bayer.mean():.1f} median={int(np.median(bayer))}")

# Demosaic. SGBRG → cv2 wants the right constant.
# Bayer pattern letters denote the 2x2 top-left arrangement:
#   SGBRG = G B / R G
# OpenCV's BAYER_GB2BGR matches that (Green-Blue top row).
bayer8 = (bayer / 4).astype(np.uint8)  # 10-bit → 8-bit quick shift for opencv demosaic
rgb = cv2.cvtColor(bayer8, cv2.COLOR_BayerGB2BGR)
print(f"demosaiced: {rgb.shape}")

# Percentile stretch. p0..p99 → 0..255 linear.
# Skip the saturated/hot pixels at the top.
p_lo = np.percentile(rgb, 1)
p_hi = np.percentile(rgb, 99.5)
print(f"stretch: {p_lo:.1f} .. {p_hi:.1f}")
stretched = np.clip((rgb.astype(np.float32) - p_lo) * 255.0 / max(1, p_hi - p_lo),
                    0, 255).astype(np.uint8)

# Save
out = "/tmp/latest_night.jpg"
cv2.imwrite(out, stretched, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(f"wrote {out}")
print(f"size: {os.path.getsize(out) // 1024} KB")
