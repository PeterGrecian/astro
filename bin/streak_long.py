#!/usr/bin/env python3
"""Long-integration streak. Designed to show star MOTION as trails.

Different from streak_render.py:
- accumulates more frames (default 600 = ~30 min)
- skips the median-subtract step that hides the motion
- log-stretches (asinh) so faint trails are visible without blowing out
  the bright pixels
"""
import glob, os, sys, time
import numpy as np
import cv2

N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
files = files[:-2][-N:]
if len(files) < 2:
    print("not enough", file=sys.stderr); sys.exit(1)

t_start = time.strftime("%H:%M:%S", time.gmtime(os.path.getmtime(files[0])))
t_end   = time.strftime("%H:%M:%S UTC", time.gmtime(os.path.getmtime(files[-1])))
span_s  = os.path.getmtime(files[-1]) - os.path.getmtime(files[0])
print(f"using {len(files)} frames ({t_start} → {t_end}, span {span_s/60:.1f} min)")

a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = np.load(files[0]).astype(np.int32)
for i, fn in enumerate(files[1:], 1):
    cur = np.load(fn).astype(np.int32)
    a_abs += np.abs(cur - prev)
    prev = cur
    if i % 100 == 0:
        print(f"  ...{i}/{len(files)-1}")

print(f"a_abs: min={int(a_abs.min())} max={int(a_abs.max())} mean={a_abs.mean():.1f}")

# Linear stretch with a true black point. We subtract a "noise floor"
# (the 80th percentile, which is the typical accumulated noise level in
# regions where no star ever transited), then linearly scale the rest.
# This keeps actually-dark sky as black and lets star streaks pop.
x = a_abs.astype(np.float32)
floor = np.percentile(x, 80)   # noise floor — pixels never visited by a star
hi    = np.percentile(x, 99.95)  # streak peaks
print(f"floor (80pct): {floor:.1f}, hi (99.95pct): {hi:.1f}")
stretched = np.clip((x - floor) * 255.0 / max(1, hi - floor), 0, 255)
img8 = stretched.astype(np.uint8)

out = "/tmp/streak_long.jpg"
cv2.imwrite(out, img8, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {out}")
