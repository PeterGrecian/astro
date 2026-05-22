#!/usr/bin/env python3
"""Rotation-compensated photon stack.

For each frame, rotate around the celestial pole so the stars align
with frame 0. Then sum. Stars become points; cloud, light leak,
sensor banding smear out.

Inputs:
  --pole-x, --pole-y : pole pixel position (default: -218, 1919 typo
                       no, we discovered (1919, -218))
  --omega-rad-s      : sidereal rotation rate in rad/s. Default = the
                       sky's 7.2921e-5 rad/s (= 2pi / 86164 s).
  --start, --end     : UTC HH:MM window
  --percentile       : darkest-N% filter (default 50)
  --csv              : brightness CSV for filtering
  --out              : output JPG
  --target-median    : stretch target (default 50)
  --downsample       : factor (default 1 = full res; 2 = half res faster)
"""
import argparse, csv, os, sys, time
from datetime import datetime
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--pole-x", type=float, default=1919)
ap.add_argument("--pole-y", type=float, default=-218)
ap.add_argument("--omega-rad-s", type=float, default=7.2921e-5)
ap.add_argument("--start", required=True)
ap.add_argument("--end", required=True)
ap.add_argument("--percentile", type=float, default=50)
ap.add_argument("--csv", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--save-npy", help="optional .npy save of raw acc")
ap.add_argument("--target-median", type=int, default=50)
ap.add_argument("--downsample", type=int, default=1)
ap.add_argument("--limit", type=int, default=0,
                help="cap on number of frames (0=no cap)")
args = ap.parse_args()

def parse_hhmm(s):
    h, m = s.split(":"); return int(h)*60+int(m)
start_m = parse_hhmm(args.start); end_m = parse_hhmm(args.end)
wraps = end_m < start_m
def in_window(iso):
    dt = datetime.fromisoformat(iso); m = dt.hour*60+dt.minute
    return (m >= start_m or m < end_m) if wraps else (start_m <= m < end_m)

rows = []
with open(args.csv) as f:
    for r in csv.DictReader(f):
        if in_window(r["iso_utc"]):
            rows.append((r["filename"], float(r["mean"]), r["iso_utc"]))
print(f"in window: {len(rows)}")
rows.sort(key=lambda r: r[1])
k = int(len(rows) * args.percentile / 100)
selected = sorted(rows[:k], key=lambda r: r[2])
if args.limit:
    selected = selected[::max(1, len(selected)//args.limit)][:args.limit]
print(f"using darkest {args.percentile}% = {len(selected)} frames")

# Reference time: first frame's mtime
ref_epoch_ms = int(os.path.basename(selected[0][0]).split(".")[0])
print(f"reference epoch_ms: {ref_epoch_ms} ({selected[0][2]})")

# Output dimensions (possibly downsampled)
H_full, W_full = 1944, 2592
H = H_full // args.downsample
W = W_full // args.downsample
acc = np.zeros((H, W), dtype=np.int64)
pole = (args.pole_x / args.downsample, args.pole_y / args.downsample)
print(f"out shape: {H}x{W}, pole in out coords: ({pole[0]:.1f}, {pole[1]:.1f})")

t0 = time.time()
for i, (fn, _, _) in enumerate(selected):
    arr = np.load(fn)
    if args.downsample > 1:
        arr = cv2.resize(arr, (W, H), interpolation=cv2.INTER_AREA)
    # Rotation angle: positive = ccw (matches our pole-upper-right
    # geometry where the sky rotates the same way clocks run from
    # northern observer's POV). We'll find the sign by trial; if
    # stars smear instead of sharpening, flip the sign of omega.
    epoch_ms = int(os.path.basename(fn).split(".")[0])
    dt_s = (epoch_ms - ref_epoch_ms) / 1000.0
    angle_rad = -args.omega_rad_s * dt_s
    angle_deg = np.degrees(angle_rad)
    # cv2.getRotationMatrix2D(center, angle_deg, scale) — angle is ccw
    M = cv2.getRotationMatrix2D(pole, angle_deg, 1.0)
    rotated = cv2.warpAffine(arr.astype(np.float32), M, (W, H),
                              flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    acc += rotated.astype(np.int64)
    if i % 200 == 0:
        print(f"  [{i}/{len(selected)}] dt={dt_s:8.1f}s angle={angle_deg:8.3f}° "
              f"acc_max={int(acc.max())}", flush=True)
print(f"summed in {time.time()-t0:.0f}s")
print(f"acc: min={int(acc.min())} max={int(acc.max())} median={int(np.median(acc))}")

if args.save_npy:
    np.save(args.save_npy, acc)
    print(f"saved {args.save_npy}")

# Stretch
med = float(np.median(acc.astype(np.float32)))
scale = args.target_median / max(1.0, med)
img8 = np.clip(acc.astype(np.float32) * scale, 0, 255).astype(np.uint8)

# Extend canvas so the off-frame pole is visible.
px, py = pole
extend_top    = max(0, int(-py) + 80) if py < 0 else 0
extend_bot    = max(0, int(py - H) + 80) if py > H else 0
extend_left   = max(0, int(-px) + 80) if px < 0 else 0
extend_right  = max(0, int(px - W) + 80) if px > W else 0
canvas_h = H + extend_top + extend_bot
canvas_w = W + extend_left + extend_right
canvas = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
canvas[extend_top:extend_top+H, extend_left:extend_left+W] = img8
canvas_bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
pp = (int(px + extend_left), int(py + extend_top))
cv2.circle(canvas_bgr, pp, 30, (0, 255, 0), 2)
cv2.line(canvas_bgr, (pp[0]-60, pp[1]), (pp[0]+60, pp[1]), (0, 255, 0), 1)
cv2.line(canvas_bgr, (pp[0], pp[1]-60), (pp[0], pp[1]+60), (0, 255, 0), 1)
cv2.putText(canvas_bgr,
            f"pole ({px*args.downsample:.0f}, {py*args.downsample:.0f})",
            (pp[0]+40, pp[1]-20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, canvas_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out} ({os.path.getsize(args.out)/1024:.0f} KB)  "
      f"canvas {canvas_w}x{canvas_h}")
