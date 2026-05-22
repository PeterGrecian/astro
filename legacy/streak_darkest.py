#!/usr/bin/env python3
"""Streak accumulator filtered by brightness percentile.

Same shape as streak_window.py but instead of fixed --bright-reject,
reads the brightness CSV and rejects frames in the top (100-K)% of
the window. Preserves time order — when a frame is rejected, the
diff baseline (prev) jumps across the gap to the next kept frame.
"""
import argparse, csv, os, sys, time
from datetime import datetime
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--start", required=True, help="UTC HH:MM")
ap.add_argument("--end", required=True, help="UTC HH:MM (wraps midnight ok)")
ap.add_argument("--percentile", type=float, default=50,
                help="keep the darkest N%% of frames in the window")
ap.add_argument("--out", required=True)
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

rows = []
with open(args.csv) as f:
    for r in csv.DictReader(f):
        if in_window(r["iso_utc"]):
            rows.append((r["filename"], float(r["mean"]), r["iso_utc"]))
print(f"in window {args.start}-{args.end}: {len(rows)} frames")

# Find the threshold (= percentile-th value of mean)
means_sorted = sorted(r[1] for r in rows)
k_idx = int(len(means_sorted) * args.percentile / 100) - 1
thresh = means_sorted[max(0, k_idx)]
print(f"keep frames with mean <= {thresh:.3f} (darkest {args.percentile}%)")

# Walk in time order
rows.sort(key=lambda r: r[2])
selected = [(fn, m) for fn, m, _ in rows if m <= thresh]
print(f"kept {len(selected)} of {len(rows)}")

a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = None
t0 = time.time()
for i, (fn, _) in enumerate(selected):
    cur = np.load(fn).astype(np.int32)
    if prev is not None:
        a_abs += np.abs(cur - prev)
    prev = cur
    if i % 200 == 0:
        print(f"  [{i}/{len(selected)}]  a_max={int(a_abs.max())}")
print(f"summed in {time.time()-t0:.1f}s")
print(f"a_abs: min={int(a_abs.min())} max={int(a_abs.max())} "
      f"median={int(np.median(a_abs))}")

# Bayer-aware split + luminance combine (same as streak_window.py)
G1 = a_abs[0::2, 0::2].astype(np.float32)
B  = a_abs[0::2, 1::2].astype(np.float32)
R  = a_abs[1::2, 0::2].astype(np.float32)
G2 = a_abs[1::2, 1::2].astype(np.float32)

def floor_norm(p):
    f = np.percentile(p, 80)
    return p / max(1.0, f)

lum = floor_norm(R) + floor_norm(G1) + floor_norm(G2) + floor_norm(B)
floor = np.percentile(lum, 50)
hi    = np.percentile(lum, 99.95)
print(f"stretch: floor={floor:.2f} hi={hi:.2f}")
stretched = np.clip((lum - floor) * 255.0 / max(0.01, hi - floor), 0, 255)
img8 = stretched.astype(np.uint8)
img_full = cv2.resize(img8, (2592, 1944), interpolation=cv2.INTER_LINEAR)
cv2.imwrite(args.out, img_full, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out} ({os.path.getsize(args.out)/1024:.0f} KB)")
