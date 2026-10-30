#!/usr/bin/env python3
"""10-90% width of the upper edge of a dark object, column by column, against the event's sky.

    edge_width.py EVENT_DIR FRAME_STEM X0 X1
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

d, stem, x0, x1 = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
fs = sorted(d.glob("*.jpg"))
bg = np.median([np.asarray(Image.open(f).convert("L"), np.float32) for f in fs[:5]], axis=0)
x = np.asarray(Image.open(d / f"{stem}.jpg").convert("L"), np.float32) - bg
ws = []
for c in range(x0, x1, 8):
    p = np.convolve(x[:, c - 4:c + 4].mean(1), np.ones(5) / 5, "same")
    bot = int(p[1200:].argmin()) + 1200
    depth = p[bot]
    if depth > -20:
        continue
    up = p[:bot][::-1]
    i90 = int(np.argmax(up > 0.9 * depth))
    i10 = int(np.argmax(up > 0.1 * depth))
    ws.append((c, bot, round(float(depth)), i10 - i90))
print("column, darkest row, depth, 10-90 width (2028 px)")
for w in ws[::6]:
    print(w)
if ws:
    a = np.array([w[3] for w in ws])
    print(f"{len(a)} columns: width p10 {np.percentile(a, 10):.0f} median {np.median(a):.0f} p90 {np.percentile(a, 90):.0f} px")
print("sky noise", round(float(x[:600, :600].std()), 2))
