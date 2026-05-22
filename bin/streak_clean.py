#!/usr/bin/env python3
"""Clean streak: demosaic + hot-pixel mask + linear stretch.

1. Build a hot-pixel map from a sample of frames by finding pixels
   that are saturated (>=1000) on >50% of frames. Mask them out before
   accumulating.
2. Accumulate |diff| across consecutive raw frames. Bayer-aware
   accumulator: keep four sub-planes (R, G1, G2, B).
3. Combine the four planes back to a half-res RGB image, stretch,
   save.
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
span_s  = os.path.getmtime(files[-1]) - os.path.getmtime(files[0])
print(f"using {len(files)} frames ({t_start} → {t_end}, span {span_s/60:.1f} min)")

# Step 1: hot-pixel map. Pixels that read >=1000 in >50% of a sample.
sample_n = min(50, len(files))
print(f"building hot map from {sample_n} sample frames...")
sat_count = np.zeros((1944, 2592), dtype=np.uint16)
step = max(1, len(files) // sample_n)
for fn in files[::step][:sample_n]:
    arr = np.load(fn)
    sat_count += (arr >= 1000)
hot_mask = (sat_count > sample_n // 2)
print(f"hot pixels: {int(hot_mask.sum())} ({100*hot_mask.sum()/hot_mask.size:.3f}%)")

# Step 2: accumulate |diff| across consecutive frames, masking hot
# pixels (set to 0 contribution).
a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = np.load(files[0]).astype(np.int32)
prev[hot_mask] = 0
for i, fn in enumerate(files[1:], 1):
    cur = np.load(fn).astype(np.int32)
    cur[hot_mask] = 0
    diff = np.abs(cur - prev)
    a_abs += diff
    prev = cur
    if i % 100 == 0:
        print(f"  ...{i}/{len(files)-1}")
print(f"a_abs (masked): min={int(a_abs.min())} max={int(a_abs.max())} "
      f"mean={a_abs.mean():.1f}")

# Step 3: Bayer-aware split into R, G1, G2, B sub-planes.
# Pattern is SGBRG (top-left 2x2): G B / R G.
#   (y=0,x=0) = G1   (y=0,x=1) = B
#   (y=1,x=0) = R    (y=1,x=1) = G2
G1 = a_abs[0::2, 0::2].astype(np.float32)   # green (top row, even col)
B  = a_abs[0::2, 1::2].astype(np.float32)   # blue
R  = a_abs[1::2, 0::2].astype(np.float32)   # red
G2 = a_abs[1::2, 1::2].astype(np.float32)   # green (bottom row, odd col)
G  = (G1 + G2) * 0.5                         # combined green

# Normalise each channel by its own noise floor so the green-double
# bias disappears.
def stretch(plane, lo_p=80, hi_p=99.95):
    lo = np.percentile(plane, lo_p)
    hi = np.percentile(plane, hi_p)
    out = np.clip((plane - lo) * 255.0 / max(1, hi - lo), 0, 255)
    return out.astype(np.uint8)

R8 = stretch(R)
G8 = stretch(G)
B8 = stretch(B)
rgb = np.dstack([R8, G8, B8])  # (H/2, W/2, 3)
print(f"rgb shape: {rgb.shape}")

# Optional: upscale to original size for viewing parity
rgb_full = cv2.resize(rgb, (2592, 1944), interpolation=cv2.INTER_LINEAR)

# OpenCV writes BGR
bgr = rgb_full[:, :, ::-1]
out = "/tmp/streak_clean.jpg"
cv2.imwrite(out, bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {out}")
