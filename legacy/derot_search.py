#!/usr/bin/env python3
"""Grid search over (pole_x, pole_y, omega) to maximise stack sharpness.

Sharpness metric: max(acc) — the brightest pixel after stacking. When
parameters are right, ALL the frames of one bright star land on the
same pixel, multiplying its brightness by N. When wrong, the star's
light is spread → max is low.

Uses a small subset of frames for speed. Once we find the best grid
cell we can fine-search around it.
"""
import argparse, csv, os, sys, time
from datetime import datetime
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--start", required=True)
ap.add_argument("--end", required=True)
ap.add_argument("--percentile", type=float, default=50)
ap.add_argument("--n-frames", type=int, default=100,
                help="random subsample for speed")
ap.add_argument("--downsample", type=int, default=4,
                help="larger = faster but lower resolution sharpness")
# Search ranges
ap.add_argument("--pole-x-min", type=float, default=1500)
ap.add_argument("--pole-x-max", type=float, default=2200)
ap.add_argument("--pole-x-steps", type=int, default=5)
ap.add_argument("--pole-y-min", type=float, default=-500)
ap.add_argument("--pole-y-max", type=float, default=100)
ap.add_argument("--pole-y-steps", type=int, default=5)
ap.add_argument("--omega-min", type=float, default=-2.0e-4)
ap.add_argument("--omega-max", type=float, default=2.0e-4)
ap.add_argument("--omega-steps", type=int, default=9)
ap.add_argument("--out-csv", required=True)
args = ap.parse_args()

# Load frames in window
def parse_hhmm(s):
    h, m = s.split(":"); return int(h)*60+int(m)
sm = parse_hhmm(args.start); em = parse_hhmm(args.end)
wraps = em < sm
def in_window(iso):
    dt = datetime.fromisoformat(iso); m = dt.hour*60+dt.minute
    return (m >= sm or m < em) if wraps else (sm <= m < em)
rows = []
with open(args.csv) as f:
    for r in csv.DictReader(f):
        if in_window(r["iso_utc"]):
            rows.append((r["filename"], float(r["mean"]), r["iso_utc"]))
rows.sort(key=lambda r: r[1])
k = int(len(rows) * args.percentile / 100)
selected = sorted(rows[:k], key=lambda r: r[2])
print(f"darkest {args.percentile}%: {len(selected)}")
# Subsample
if len(selected) > args.n_frames:
    step = len(selected) // args.n_frames
    selected = selected[::step][:args.n_frames]
print(f"using {len(selected)} sample frames")

# Preload all frames (subset is small)
H_full, W_full = 1944, 2592
H = H_full // args.downsample
W = W_full // args.downsample
frames = []
ref_epoch_ms = int(os.path.basename(selected[0][0]).split(".")[0])
for fn, _, _ in selected:
    arr = np.load(fn)
    if args.downsample > 1:
        arr = cv2.resize(arr, (W, H), interpolation=cv2.INTER_AREA)
    epoch_ms = int(os.path.basename(fn).split(".")[0])
    dt_s = (epoch_ms - ref_epoch_ms) / 1000.0
    frames.append((arr.astype(np.float32), dt_s))
print(f"preloaded {len(frames)} frames @ {W}x{H}")

# Grid search
xs = np.linspace(args.pole_x_min, args.pole_x_max, args.pole_x_steps)
ys = np.linspace(args.pole_y_min, args.pole_y_max, args.pole_y_steps)
ws = np.linspace(args.omega_min, args.omega_max, args.omega_steps)
print(f"grid: {len(xs)} × {len(ys)} × {len(ws)} = "
      f"{len(xs)*len(ys)*len(ws)} cells")

results = []
t0 = time.time()
n_done = 0
total = len(xs) * len(ys) * len(ws)
for px in xs:
    for py in ys:
        for omega in ws:
            acc = np.zeros((H, W), dtype=np.float32)
            pole_ds = (px / args.downsample, py / args.downsample)
            for arr, dt_s in frames:
                angle_deg = np.degrees(omega * dt_s)
                M = cv2.getRotationMatrix2D(pole_ds, angle_deg, 1.0)
                rot = cv2.warpAffine(arr, M, (W, H),
                                      flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT,
                                      borderValue=0)
                acc += rot
            sharp_max = float(acc.max())
            sharp_var = float(acc.var())
            results.append((px, py, omega, sharp_max, sharp_var))
            n_done += 1
            if n_done % 10 == 0:
                el = time.time() - t0
                print(f"  [{n_done}/{total}] px={px:.0f} py={py:.0f} "
                      f"omega={omega:.2e}  max={sharp_max:.0f}  "
                      f"var={sharp_var:.0f}  elapsed {el:.0f}s", flush=True)

# Sort by sharpness
results.sort(key=lambda r: -r[3])
print()
print("TOP 10 BY max:")
for r in results[:10]:
    print(f"  px={r[0]:7.0f} py={r[1]:7.0f} omega={r[2]:+.3e}  "
          f"max={r[3]:9.0f}  var={r[4]:9.0f}")

with open(args.out_csv, "w") as f:
    f.write("pole_x,pole_y,omega,sharp_max,sharp_var\n")
    for r in results:
        f.write(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}\n")
print(f"\nwrote {args.out_csv}")
