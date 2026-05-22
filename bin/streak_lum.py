#!/usr/bin/env python3
"""Streak via luminance: accumulate, demosaic to RGB, weighted-sum to
mono, stretch. Stars are broadband so summing channels boosts SNR.
"""
import glob, os, sys, time
import numpy as np
import cv2

N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
files = files[:-2][-N:]
if len(files) < 4:
    print("not enough", file=sys.stderr); sys.exit(1)

t_start = time.strftime("%H:%M:%S", time.gmtime(os.path.getmtime(files[0])))
t_end   = time.strftime("%H:%M:%S UTC", time.gmtime(os.path.getmtime(files[-1])))
print(f"using {len(files)} frames ({t_start} → {t_end})")

# Accumulator on the raw Bayer plane.
a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = np.load(files[0]).astype(np.int32)
for i, fn in enumerate(files[1:], 1):
    cur = np.load(fn).astype(np.int32)
    a_abs += np.abs(cur - prev)
    prev = cur
    if i % 100 == 0:
        print(f"  ...{i}/{len(files)-1}")

# Split into 4 sub-planes (half-res each).
G1 = a_abs[0::2, 0::2].astype(np.float32)
B  = a_abs[0::2, 1::2].astype(np.float32)
R  = a_abs[1::2, 0::2].astype(np.float32)
G2 = a_abs[1::2, 1::2].astype(np.float32)

# Equalise channel noise floors before summing — divide each by its
# 80th percentile (which is the typical no-star-here level). After this
# all four channels are on the same scale.
def floor_norm(p):
    f = np.percentile(p, 80)
    return p / max(1.0, f)
R_n  = floor_norm(R)
G1_n = floor_norm(G1)
G2_n = floor_norm(G2)
B_n  = floor_norm(B)

# Luminance: equal weights post-normalisation
lum = R_n + G1_n + G2_n + B_n
print(f"lum: min={lum.min():.2f} max={lum.max():.2f} median={np.median(lum):.2f}")

# Stretch the luminance. Set the noise floor to true black.
floor = np.percentile(lum, 50)
hi    = np.percentile(lum, 99.95)
print(f"stretch: floor={floor:.2f} hi={hi:.2f}")
stretched = np.clip((lum - floor) * 255.0 / max(0.01, hi - floor), 0, 255)
img8 = stretched.astype(np.uint8)

# Upscale to full sensor resolution for viewing parity.
img_full = cv2.resize(img8, (2592, 1944), interpolation=cv2.INTER_LINEAR)
out = "/tmp/streak_lum.jpg"
cv2.imwrite(out, img_full, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {out}")
