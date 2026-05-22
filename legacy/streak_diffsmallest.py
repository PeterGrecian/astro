#!/usr/bin/env python3
"""Streak accumulator that keeps the darkest abs-diff contributions.

Algorithm:
  1. Walk frames in time order. For each consecutive pair, compute
     |frame_n - frame_{n-1}|.mean() and stash that scalar + the
     frame pointers.
  2. Sort the diff records by that mean. Take the bottom K%.
  3. For each kept record, add |frame_n - frame_{n-1}| to the
     accumulator.

This rejects ANY frame transition that's globally hot — bright
flashes, column-bias glitches, anything that elevates the whole-frame
|diff|.mean(). More robust than filtering by frame brightness alone.

Cost: we have to compute the diff once to get its mean (the cheap
pass), then re-compute it to add to the accumulator (the expensive
pass). Could cache the diff arrays in RAM but at 5000 × 10 MB = 50 GB
that's too much. Do two passes.

Optimisation: read the brightness CSV's diff_mean column if it
exists, skips the first pass.
"""
import argparse, csv, os, sys, time
from datetime import datetime
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--start", required=True)
ap.add_argument("--end", required=True)
ap.add_argument("--percentile", type=float, default=50)
ap.add_argument("--csv", help="brightness CSV (used for time window)")
ap.add_argument("--diff-csv",
                help="optional pre-computed diff_means.csv "
                     "(epoch_ms_b, diff_mean) — skips the first pass")
ap.add_argument("--out", required=True)
args = ap.parse_args()

def parse_hhmm(s):
    h, m = s.split(":"); return int(h)*60+int(m)

start_m, end_m = parse_hhmm(args.start), parse_hhmm(args.end)
wraps = end_m < start_m
def in_window(iso):
    dt = datetime.fromisoformat(iso); m = dt.hour*60 + dt.minute
    return (m >= start_m or m < end_m) if wraps else (start_m <= m < end_m)

rows = []
with open(args.csv) as f:
    for r in csv.DictReader(f):
        if in_window(r["iso_utc"]):
            rows.append((r["filename"], r["iso_utc"]))
rows.sort(key=lambda r: r[1])
print(f"in window {args.start}-{args.end}: {len(rows)} frames")

# Pass 1: compute diff_mean for each consecutive pair (or load from CSV).
diff_records = []   # list of (idx_b, diff_mean)
if args.diff_csv and os.path.exists(args.diff_csv):
    print(f"loading diff_means from {args.diff_csv}")
    with open(args.diff_csv) as f:
        for r in csv.DictReader(f):
            diff_records.append((int(r["idx"]), float(r["diff_mean"])))
else:
    print("computing diff_means (pass 1)...")
    t0 = time.time()
    prev = None
    for i, (fn, _) in enumerate(rows):
        cur = np.load(fn).astype(np.int32)
        if prev is not None:
            dm = float(np.abs(cur - prev).mean())
            diff_records.append((i, dm))
        prev = cur
        if i % 500 == 0:
            print(f"  [{i}/{len(rows)}] elapsed {time.time()-t0:.0f}s")
    print(f"pass 1: {time.time()-t0:.0f}s")

# Filter: take the diffs with the K%-lowest diff_mean
diff_records.sort(key=lambda r: r[1])
k = int(len(diff_records) * args.percentile / 100)
selected = sorted(diff_records[:k], key=lambda r: r[0])
print(f"darkest {args.percentile}% of diffs: {k} pairs "
      f"(threshold diff_mean = {diff_records[k-1][1]:.3f})")

# Pass 2: re-compute the selected diffs and accumulate
print("accumulating (pass 2)...")
t0 = time.time()
a_abs = np.zeros((1944, 2592), dtype=np.int64)
for j, (idx_b, _) in enumerate(selected):
    fn_a, _ = rows[idx_b - 1]
    fn_b, _ = rows[idx_b]
    a = np.load(fn_a).astype(np.int32)
    b = np.load(fn_b).astype(np.int32)
    a_abs += np.abs(b - a)
    if j % 200 == 0:
        print(f"  [{j}/{len(selected)}] a_max={int(a_abs.max())}")
print(f"pass 2: {time.time()-t0:.0f}s")
print(f"a_abs: min={int(a_abs.min())} max={int(a_abs.max())} "
      f"median={int(np.median(a_abs))}")

# Same luminance stretch as streak_darkest.py
G1 = a_abs[0::2, 0::2].astype(np.float32)
B  = a_abs[0::2, 1::2].astype(np.float32)
R  = a_abs[1::2, 0::2].astype(np.float32)
G2 = a_abs[1::2, 1::2].astype(np.float32)
def floor_norm(p):
    f = np.percentile(p, 80); return p / max(1.0, f)
lum = floor_norm(R) + floor_norm(G1) + floor_norm(G2) + floor_norm(B)
floor = np.percentile(lum, 50)
hi    = np.percentile(lum, 99.95)
print(f"stretch: floor={floor:.2f} hi={hi:.2f}")
stretched = np.clip((lum - floor) * 255.0 / max(0.01, hi - floor), 0, 255)
img_full = cv2.resize(stretched.astype(np.uint8), (2592, 1944),
                       interpolation=cv2.INTER_LINEAR)
cv2.imwrite(args.out, img_full, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out}")
