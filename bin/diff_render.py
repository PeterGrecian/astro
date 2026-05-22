#!/usr/bin/env python3
"""Render an absolute-difference between two frames N apart.

Stars move (sidereal drift); aircraft/satellites streak; cloud edges
change slowly. The diff lights up anything that moved between the two
captures and zeros out anything that didn't.
"""
import glob, os, sys, time
import numpy as np
import cv2

GAP = 20  # frames apart. At ~3 s cadence: 60 s separation. Stars at zenith
          # drift ~9 arcsec/s × 60 s = 540 arcsec ~ 7 px at 74 arcsec/px.

files = sorted(glob.glob("/home/peter/starcam-frames/night/raw/*/*/*.npy"))
if len(files) < GAP + 2:
    print(f"need {GAP+2} frames, have {len(files)}", file=sys.stderr); sys.exit(1)

# Avoid the very newest (mid-write) — take frames at -2 and -2-GAP
target = files[-2]
prior  = files[-2 - GAP]
print(f"cur:   {target}")
print(f"       mtime {time.strftime('%H:%M:%S UTC', time.gmtime(os.path.getmtime(target)))}")
print(f"prior: {prior}")
print(f"       mtime {time.strftime('%H:%M:%S UTC', time.gmtime(os.path.getmtime(prior)))}")
print(f"gap: {GAP} frames")

cur = np.load(target).astype(np.int32)
old = np.load(prior).astype(np.int32)

diff = np.abs(cur - old).astype(np.uint16)
print(f"diff: min={int(diff.min())} max={int(diff.max())} "
      f"mean={diff.mean():.2f} median={int(np.median(diff))}")

# Demosaic the diff treating Bayer as monochrome — at this scale the
# Bayer pattern is invisible noise. Just stretch and save.
p_lo = np.percentile(diff, 50)   # median = "no change" baseline
p_hi = np.percentile(diff, 99.9) # bright tail
print(f"stretch: {p_lo:.1f} .. {p_hi:.1f}")

stretched = np.clip((diff.astype(np.float32) - p_lo) * 255.0 / max(1, p_hi - p_lo),
                    0, 255).astype(np.uint8)
out = "/tmp/latest_diff.jpg"
cv2.imwrite(out, stretched, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(f"wrote {out}")
print(f"size: {os.path.getsize(out) // 1024} KB")

# Also: pixels >50 above baseline = strong "something moved here"
strong = int((diff > 50).sum())
print(f"strong-diff pixels (>50): {strong:>8d} ({100*strong/diff.size:.4f}%)")
