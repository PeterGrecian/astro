#!/usr/bin/env python3
"""Walk every .npy frame in a starcam night dir, emit a CSV of
per-frame brightness stats. One row per frame, cheap to re-slice
later for plots or "find the bright outliers" queries.

Columns:
  epoch_ms  iso_utc  filename  mean  median  p95  max  bright_pixels
where bright_pixels = count of pixels >= 500 (a "something hot in this
frame" signal — bright stars, aircraft lights, hot pixels).
"""
import argparse, csv, glob, os, sys, time
from datetime import datetime, timezone
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--frames-dir",
                default="/home/peter/starcam-frames/night/raw")
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=0,
                help="cap (0 = all)")
args = ap.parse_args()

files = sorted(glob.glob(f"{args.frames_dir}/*/*/*.npy"))
print(f"{len(files)} frames total", flush=True)
if args.limit:
    files = files[:args.limit]
    print(f"limited to {len(files)}", flush=True)

t0 = time.time()
with open(args.out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["epoch_ms", "iso_utc", "filename",
                "mean", "median", "p95", "max", "bright_pixels"])
    for i, fn in enumerate(files):
        try:
            arr = np.load(fn)
        except Exception as e:
            print(f"  [{i}] FAIL {fn}: {e}", file=sys.stderr)
            continue
        epoch_ms = int(os.path.basename(fn).split(".")[0])
        iso = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()
        mean = float(arr.mean())
        median = float(np.median(arr))
        p95 = float(np.percentile(arr, 95))
        mx = int(arr.max())
        bright = int((arr >= 500).sum())
        w.writerow([epoch_ms, iso, fn, f"{mean:.3f}", f"{median:.1f}",
                    f"{p95:.1f}", mx, bright])
        if i % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            eta = (len(files) - i - 1) / rate if rate else 0
            print(f"  [{i}/{len(files)}] {fn.split('/')[-1]} "
                  f"mean={mean:.1f} max={mx} bright={bright} "
                  f"({rate:.1f} fps, ETA {eta/60:.1f} min)", flush=True)
print(f"wrote {args.out} in {time.time()-t0:.1f}s", flush=True)
