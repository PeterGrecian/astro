#!/usr/bin/env python3
"""Photon-sum the darkest K% of frames in a time window.

Reads the brightness CSV, filters to the window, sorts by mean
ascending, takes the bottom K%. Sums those frames (no bias
subtraction — gives a true photon count we can stretch as we like).
"""
import argparse, csv, os, sys, time
from datetime import datetime, timezone
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--start", required=True, help="UTC HH:MM")
ap.add_argument("--end", required=True, help="UTC HH:MM (wraps midnight ok)")
ap.add_argument("--percentile", type=float, default=50,
                help="keep the darkest N%% of frames in the window")
ap.add_argument("--out", required=True)
ap.add_argument("--target-median", type=int, default=50,
                help="output stretches so sum-median lands here (0-255)")
args = ap.parse_args()

def parse_hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)

start_m = parse_hhmm(args.start)
end_m = parse_hhmm(args.end)
wraps = end_m < start_m

def in_window(iso):
    dt = datetime.fromisoformat(iso)
    m = dt.hour * 60 + dt.minute
    if wraps:
        return m >= start_m or m < end_m
    return start_m <= m < end_m

# Load CSV → list of (filename, mean) in window
rows = []
with open(args.csv) as f:
    for r in csv.DictReader(f):
        if in_window(r["iso_utc"]):
            rows.append((r["filename"], float(r["mean"])))
print(f"in window {args.start}-{args.end}: {len(rows)} frames")

# Sort by mean ascending, take darkest K%
rows.sort(key=lambda x: x[1])
k = int(len(rows) * args.percentile / 100)
selected = rows[:k]
print(f"darkest {args.percentile}%: {len(selected)} frames "
      f"(mean threshold: {selected[-1][1]:.3f})")

# Sum
acc = np.zeros((1944, 2592), dtype=np.int64)
t0 = time.time()
for i, (fn, _) in enumerate(selected):
    acc += np.load(fn).astype(np.int32)
    if i % 200 == 0:
        print(f"  [{i}/{len(selected)}]")
print(f"summed in {time.time()-t0:.1f}s")
print(f"acc: min={int(acc.min())} max={int(acc.max())} "
      f"mean={acc.mean():.1f} median={int(np.median(acc))}")

med = float(np.median(acc.astype(np.float32)))
scale = args.target_median / max(1.0, med)
print(f"stretch: median {med:.1f} → grey {args.target_median} (scale {scale:.4f})")
img8 = np.clip(acc.astype(np.float32) * scale, 0, 255).astype(np.uint8)
cv2.imwrite(args.out, img8, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out} ({os.path.getsize(args.out)/1024:.0f} KB)")
