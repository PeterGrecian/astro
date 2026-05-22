#!/usr/bin/env python3
"""Build a hot-pixel map: pixels saturated in >50% of a sample of frames."""
import argparse, glob, os, sys
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--frames-dir", default="/home/peter/starcam-frames/night/raw")
ap.add_argument("--out", required=True)
ap.add_argument("--n-frames", type=int, default=200)
ap.add_argument("--threshold", type=int, default=900,
                help="pixel >=this counts as saturated")
ap.add_argument("--min-fraction", type=float, default=0.5,
                help="fraction of frames pixel must saturate in")
args = ap.parse_args()

# Use dark hours only (UTC 23-02), randomly spaced
files = sorted(glob.glob(f"{args.frames_dir}/*/*/*.npy"))
dark_files = []
for f in files:
    import time
    mt = time.gmtime(os.path.getmtime(f))
    if 23 <= mt.tm_hour or mt.tm_hour < 2:
        dark_files.append(f)
step = max(1, len(dark_files) // args.n_frames)
sample = dark_files[::step][:args.n_frames]
print(f"sampling {len(sample)} of {len(dark_files)} dark frames")

H, W = 1944, 2592
sat_count = np.zeros((H, W), dtype=np.uint16)
for i, fn in enumerate(sample):
    arr = np.load(fn)
    sat_count += (arr >= args.threshold)
    if i % 50 == 0:
        print(f"  [{i}/{len(sample)}]")

threshold_count = int(len(sample) * args.min_fraction)
hot_mask = (sat_count >= threshold_count)
print(f"hot pixels (saturated in >={args.min_fraction*100:.0f}%): {int(hot_mask.sum())}")
np.save(args.out, hot_mask.astype(np.uint8))
print(f"wrote {args.out}")
