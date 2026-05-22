#!/usr/bin/env python3
"""Produce a series of N-minute-averaged frames over a time window.

Each chunk is the MEAN of all frames whose mtime falls in the chunk's
time slot. Star drift across N minutes at zenith ≈ (N×60 × 9 arcsec/s)
/ 74 arcsec/px ≈ 7.3 × N pixels — so 10 min gives ~73 px arcs, short
enough that bright stars still cluster but visible as elongated dots.

Per-chunk stretch: clip below the 2nd percentile, scale so the 99.5th
percentile lands at 255. Keeps contrast consistent across the chunks.

Outputs: <out_dir>/chunk_HH-MM.jpg, one per chunk.
"""
import argparse, glob, os, sys, time
from datetime import datetime, timedelta, timezone
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("start", help="UTC HH:MM start")
ap.add_argument("end", help="UTC HH:MM end (wraps midnight ok)")
ap.add_argument("--out-dir", required=True)
ap.add_argument("--frames-dir", default="/home/peter/starcam-frames/night/raw")
ap.add_argument("--minutes", type=int, default=10,
                help="chunk length in minutes")
ap.add_argument("--bright-reject", type=float, default=50)
ap.add_argument("--date", default="2026-05-20",
                help="date of the start time (UTC); end wraps to +1 day if needed")
args = ap.parse_args()

os.makedirs(args.out_dir, exist_ok=True)

start_dt = datetime.fromisoformat(f"{args.date}T{args.start}:00+00:00")
# parse end: if HH < start.HH, add one day
end_h, end_m = map(int, args.end.split(":"))
end_dt = start_dt.replace(hour=end_h, minute=end_m, second=0)
if end_dt <= start_dt:
    end_dt += timedelta(days=1)
print(f"window: {start_dt} → {end_dt}")

# Enumerate all candidate files once
files = sorted(glob.glob(f"{args.frames_dir}/*/*/*.npy"))[:-2]
# Pre-bucket by chunk_idx
chunks = {}  # idx -> [files]
for fn in files:
    mt = datetime.fromtimestamp(os.path.getmtime(fn), tz=timezone.utc)
    if mt < start_dt or mt >= end_dt:
        continue
    idx = int((mt - start_dt).total_seconds() // (args.minutes * 60))
    chunks.setdefault(idx, []).append(fn)

print(f"chunks populated: {len(chunks)}")
for idx in sorted(chunks):
    t = start_dt + timedelta(minutes=idx * args.minutes)
    fs = chunks[idx]
    if len(fs) < 5:
        print(f"  chunk {idx} ({t.strftime('%H:%M')}): only {len(fs)} frames, skip")
        continue
    print(f"  chunk {idx} ({t.strftime('%H:%M')}): {len(fs)} frames", flush=True)

    acc = np.zeros((1944, 2592), dtype=np.int64)
    used = 0
    for fn in fs:
        arr = np.load(fn)
        if args.bright_reject and arr.mean() > args.bright_reject:
            continue
        acc += arr.astype(np.int32)
        used += 1
    if used < 5:
        print(f"     after reject: only {used} frames, skip")
        continue
    # Per-frame mean (not sum) so columns don't blow up
    mean_frame = (acc / used).astype(np.float32)

    # Stretch: 2nd → 99.5th percentile → 0..255
    lo = np.percentile(mean_frame, 2)
    hi = np.percentile(mean_frame, 99.5)
    print(f"     used={used} stretch={lo:.1f}..{hi:.1f}", flush=True)
    img8 = np.clip((mean_frame - lo) * 255.0 / max(0.01, hi - lo),
                   0, 255).astype(np.uint8)

    out = f"{args.out_dir}/chunk_{t.strftime('%H-%M')}.jpg"
    cv2.imwrite(out, img8, [cv2.IMWRITE_JPEG_QUALITY, 90])

print("done")
