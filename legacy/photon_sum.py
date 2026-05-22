#!/usr/bin/env python3
"""Sum (not abs-diff!) frames over a window. Photon-accumulation, not
streak accumulation.

Per frame: optionally subtract the per-frame median (sensor bias),
then add to the sum. Output stretched so that sum's median lands at
8-bit grey-50 — visible-but-not-blown.

NB: stars DRIFT during the sum (no rotation comp), so they'll trace
arcs like in the streak images, BUT the total light each arc receives
scales with N — much brighter total signal.
"""
import argparse, glob, os, sys, time
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("start", help="UTC HH:MM start")
ap.add_argument("end", help="UTC HH:MM end (wraps midnight ok)")
ap.add_argument("--out", required=True)
ap.add_argument("--frames-dir", default="/home/peter/starcam-frames/night/raw")
ap.add_argument("--bright-reject", type=float, default=50,
                help="skip frames with mean > this (drops twilight/glow)")
ap.add_argument("--no-bias", action="store_true",
                help="don't subtract per-frame median before summing")
ap.add_argument("--target-median", type=int, default=50,
                help="output stretches so sum-median lands here (0-255)")
args = ap.parse_args()

def parse_hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)

start_min = parse_hhmm(args.start)
end_min = parse_hhmm(args.end)
wraps = end_min < start_min

def in_window(t):
    m = t.tm_hour * 60 + t.tm_min
    if wraps:
        return m >= start_min or m < end_min
    return start_min <= m < end_min

files = sorted(glob.glob(f"{args.frames_dir}/*/*/*.npy"))
selected = [f for f in files[:-2]
            if in_window(time.gmtime(os.path.getmtime(f)))]
print(f"in window {args.start}-{args.end}: {len(selected)} frames")
if len(selected) < 2:
    print("not enough", file=sys.stderr); sys.exit(1)

t_start = time.strftime("%H:%M:%S", time.gmtime(os.path.getmtime(selected[0])))
t_end = time.strftime("%H:%M:%S UTC", time.gmtime(os.path.getmtime(selected[-1])))
print(f"span: {t_start} → {t_end}")

# Sum is int64 to be safe (5400 frames × 1023 = 5.5M, well under int64).
acc = np.zeros((1944, 2592), dtype=np.int64)
n_used = 0
n_skipped = 0
t0 = time.time()
for i, fn in enumerate(selected):
    arr = np.load(fn)
    m = float(arr.mean())
    if args.bright_reject and m > args.bright_reject:
        n_skipped += 1
        if i % 500 == 0:
            print(f"  [{i}/{len(selected)}] skip mean={m:.1f}")
        continue
    a32 = arr.astype(np.int32)
    if not args.no_bias:
        # Subtract this frame's median — removes sensor bias offset
        # so the sum captures only "above-baseline" light.
        a32 = a32 - int(np.median(arr))
    acc += a32
    n_used += 1
    if i % 500 == 0:
        print(f"  [{i}/{len(selected)}] mean={m:.1f} "
              f"acc_max={int(acc.max())} acc_median={int(np.median(acc))} "
              f"used={n_used} skipped={n_skipped}")

print(f"used: {n_used}, skipped: {n_skipped}, elapsed: {time.time()-t0:.1f}s")
print(f"acc: min={int(acc.min())} max={int(acc.max())} "
      f"mean={acc.mean():.1f} median={int(np.median(acc))}")

# Stretch so acc-median → target-median (e.g. 50).
acc_f = acc.astype(np.float32)
med = float(np.median(acc_f))
# Pixels at acc-median become args.target_median in output.
# Linear scale: out = (acc - 0) × (target_median / med) for positive,
# clipping at 255. Negative values (where bias-subtract overshot) clip to 0.
scale = args.target_median / max(1.0, med)
print(f"stretch: median {med:.1f} → grey {args.target_median}, scale={scale:.4f}")
stretched = np.clip(acc_f * scale, 0, 255).astype(np.uint8)

# Treat as monochrome for the sum (Bayer artefacts are real but
# small relative to the signal we care about at this scale).
cv2.imwrite(args.out, stretched, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out} ({os.path.getsize(args.out)/1024:.0f} KB)")
