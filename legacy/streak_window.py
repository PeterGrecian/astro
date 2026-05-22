#!/usr/bin/env python3
"""Accumulate |diff| across a time window. Designed for the morning-
after analysis on a night's worth of frames.

Usage:
    streak_window.py START_UTC_HHMM END_UTC_HHMM [--out PATH]
    streak_window.py 22:30 04:30
    streak_window.py 23:00 23:30 --out /tmp/short.jpg

Finds all frames in /home/peter/starcam-frames/night/raw/ whose mtime
falls in the requested UTC window (wraps midnight if start > end).
"""
import argparse, glob, os, sys, time
from datetime import datetime, timezone
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("start", help="UTC HH:MM start")
ap.add_argument("end", help="UTC HH:MM end (may wrap past midnight)")
ap.add_argument("--out", default="/tmp/streak.jpg")
ap.add_argument("--frames-dir", default="/home/peter/starcam-frames/night/raw")
ap.add_argument("--max-frames", type=int, default=0,
                help="cap (0 = no cap)")
ap.add_argument("--bright-reject", type=float, default=0,
                help="skip frames whose mean exceeds this (post-stat). "
                     "Use 50-100 to filter twilight/glow")
args = ap.parse_args()

def parse_hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)

start_min = parse_hhmm(args.start)
end_min = parse_hhmm(args.end)
wraps = end_min < start_min   # e.g. 22:30 → 04:30 wraps

def in_window(t_struct):
    m = t_struct.tm_hour * 60 + t_struct.tm_min
    if wraps:
        return m >= start_min or m < end_min
    return start_min <= m < end_min

files = sorted(glob.glob(f"{args.frames_dir}/*/*/*.npy"))
print(f"available: {len(files)} frames")

# Skip the very newest (might be mid-write)
selected = []
for f in files[:-2]:
    mt = time.gmtime(os.path.getmtime(f))
    if in_window(mt):
        selected.append(f)
print(f"in window {args.start}-{args.end} UTC: {len(selected)} frames")

if args.max_frames and len(selected) > args.max_frames:
    step = len(selected) // args.max_frames
    selected = selected[::step]
    print(f"subsampled to {len(selected)} (step={step})")

if len(selected) < 2:
    print("not enough", file=sys.stderr); sys.exit(1)

t_start = time.strftime("%H:%M:%S", time.gmtime(os.path.getmtime(selected[0])))
t_end = time.strftime("%H:%M:%S UTC", time.gmtime(os.path.getmtime(selected[-1])))
print(f"span: {t_start} → {t_end}")

a_abs = np.zeros((1944, 2592), dtype=np.int64)
prev = None
prev_mean = 0
n_accumulated = 0
n_skipped = 0
t0 = time.time()
for i, fn in enumerate(selected):
    cur = np.load(fn).astype(np.int32)
    cur_mean = cur.mean()
    if args.bright_reject and cur_mean > args.bright_reject:
        n_skipped += 1
        # Don't update prev — keeps the diff baseline valid across the gap
        if i % 200 == 0:
            print(f"  [{i}/{len(selected)}] skip mean={cur_mean:.1f}")
        continue
    if prev is not None:
        a_abs += np.abs(cur - prev)
        n_accumulated += 1
    prev = cur
    if i % 200 == 0:
        print(f"  [{i}/{len(selected)}] mean={cur_mean:.1f} a_max={int(a_abs.max())}")

print(f"accumulated: {n_accumulated}, skipped: {n_skipped}")
print(f"elapsed: {time.time()-t0:.1f}s")
print(f"a_abs: min={int(a_abs.min())} max={int(a_abs.max())} "
      f"mean={a_abs.mean():.1f} median={int(np.median(a_abs))}")

# Bayer-aware: split into 4 sub-planes; sum normalised.
G1 = a_abs[0::2, 0::2].astype(np.float32)
B  = a_abs[0::2, 1::2].astype(np.float32)
R  = a_abs[1::2, 0::2].astype(np.float32)
G2 = a_abs[1::2, 1::2].astype(np.float32)

def floor_norm(p):
    f = np.percentile(p, 80)
    return p / max(1.0, f)

lum = floor_norm(R) + floor_norm(G1) + floor_norm(G2) + floor_norm(B)
print(f"lum: min={lum.min():.2f} max={lum.max():.2f} median={np.median(lum):.2f}")

floor = np.percentile(lum, 50)
hi    = np.percentile(lum, 99.95)
print(f"stretch: floor={floor:.2f} hi={hi:.2f}")
stretched = np.clip((lum - floor) * 255.0 / max(0.01, hi - floor), 0, 255)
img8 = stretched.astype(np.uint8)
img_full = cv2.resize(img8, (2592, 1944), interpolation=cv2.INTER_LINEAR)
cv2.imwrite(args.out, img_full, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out}  ({os.path.getsize(args.out)/1024:.0f} KB)")
