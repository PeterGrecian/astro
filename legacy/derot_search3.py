#!/usr/bin/env python3
"""Grid search v3: aggressive dark-subtract + window-frame mask.

Subtracts the full per-pixel median (not just hot-pixel mask) from
every frame. Masks the bottom 30% and right 15% (window frame +
light leak). Variance metric on the masked region.

Result: only sky-region, non-static signal contributes. Variance
peaks where stars align coherently.
"""
import argparse, csv, os, sys, time
from datetime import datetime
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--dark-frame", required=True)
ap.add_argument("--start", required=True)
ap.add_argument("--end", required=True)
ap.add_argument("--percentile", type=float, default=50)
ap.add_argument("--n-frames", type=int, default=80)
ap.add_argument("--downsample", type=int, default=4)
ap.add_argument("--pole-x-min", type=float, default=1500)
ap.add_argument("--pole-x-max", type=float, default=2300)
ap.add_argument("--pole-x-steps", type=int, default=5)
ap.add_argument("--pole-y-min", type=float, default=-500)
ap.add_argument("--pole-y-max", type=float, default=100)
ap.add_argument("--pole-y-steps", type=int, default=5)
ap.add_argument("--omega-min", type=float, default=-2.0e-4)
ap.add_argument("--omega-max", type=float, default=2.0e-4)
ap.add_argument("--omega-steps", type=int, default=9)
ap.add_argument("--out-csv", required=True)
ap.add_argument("--out-best-acc", default=None,
                help="save .npy of best-cell accumulator")
args = ap.parse_args()

dark = np.load(args.dark_frame)
H_full, W_full = dark.shape
H = H_full // args.downsample
W = W_full // args.downsample
dark_ds = cv2.resize(dark.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
print(f"dark frame: max={dark.max():.0f}")

# Window
def parse_hhmm(s):
    h, m = s.split(":"); return int(h)*60+int(m)
sm = parse_hhmm(args.start); em = parse_hhmm(args.end); wraps = em<sm
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
if len(selected) > args.n_frames:
    step = len(selected) // args.n_frames
    selected = selected[::step][:args.n_frames]
print(f"using {len(selected)} sample frames")

ref_epoch_ms = int(os.path.basename(selected[0][0]).split(".")[0])
frames = []
for fn, _, _ in selected:
    arr = np.load(fn).astype(np.float32)
    if args.downsample > 1:
        arr = cv2.resize(arr, (W, H), interpolation=cv2.INTER_AREA)
    arr -= dark_ds        # bias + hot
    arr = np.maximum(arr, 0)
    epoch_ms = int(os.path.basename(fn).split(".")[0])
    dt_s = (epoch_ms - ref_epoch_ms) / 1000.0
    frames.append((arr, dt_s))
print("preloaded + dark-subtracted")

# Sky-only mask (everything but bottom 30% + right 15%)
sky_mask = np.zeros((H, W), dtype=bool)
sky_mask[:int(H*0.70), :int(W*0.85)] = True
print(f"sky region: {int(sky_mask.sum())} px ({100*sky_mask.sum()/sky_mask.size:.0f}%)")

xs = np.linspace(args.pole_x_min, args.pole_x_max, args.pole_x_steps)
ys = np.linspace(args.pole_y_min, args.pole_y_max, args.pole_y_steps)
ws = np.linspace(args.omega_min, args.omega_max, args.omega_steps)
total = len(xs) * len(ys) * len(ws)
print(f"grid {len(xs)}x{len(ys)}x{len(ws)} = {total}")

results = []
best = None
t0 = time.time()
n_done = 0
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
                                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                acc += rot
            sky_acc = acc[sky_mask]
            sharp_var = float(sky_acc.var())
            sharp_max = float(sky_acc.max())
            results.append((px, py, omega, sharp_max, sharp_var))
            if best is None or sharp_var > best[1]:
                best = (sharp_var, sharp_var, acc.copy(), px, py, omega)
            n_done += 1
            if n_done % 25 == 0:
                el = time.time() - t0
                print(f"  [{n_done}/{total}]  px={px:.0f} py={py:.0f} omega={omega:+.2e}  "
                      f"var={sharp_var:.0f}  best={best[1]:.0f}  elapsed {el:.0f}s",
                      flush=True)

results.sort(key=lambda r: -r[4])
print("\nTOP 15 BY sky var:")
for r in results[:15]:
    print(f"  px={r[0]:7.0f} py={r[1]:7.0f} omega={r[2]:+.3e}  "
          f"max={r[3]:9.0f}  var={r[4]:9.0f}")

with open(args.out_csv, "w") as f:
    f.write("pole_x,pole_y,omega,sharp_max,sharp_var\n")
    for r in results:
        f.write(",".join(map(str, r)) + "\n")
print(f"wrote {args.out_csv}")

if args.out_best_acc:
    _, _, best_acc, bx, by, bw = best
    np.save(args.out_best_acc, best_acc)
    print(f"wrote {args.out_best_acc}  best=(px={bx:.0f}, py={by:.0f}, omega={bw:+.3e})")
