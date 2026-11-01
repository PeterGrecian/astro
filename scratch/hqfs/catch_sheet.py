#!/usr/bin/env python3
"""For a plane_catch event: the frame differing most from the event's first frames, with a crop.

    catch_sheet.py EVENT_DIR OUT_PREFIX
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

d, out = Path(sys.argv[1]), sys.argv[2]
fs = sorted(d.glob("*.jpg"))
bg = np.median([np.asarray(Image.open(f).convert("L"), np.float32) for f in fs[:5]], axis=0)
best = (0, None, None)
hit = []
for f in fs:
    x = np.asarray(Image.open(f).convert("L"), np.float32) - bg
    a = np.abs(x)
    n = int((a > 12).sum())
    hit.append(n)
    if n >= best[0]:
        best = (n, f, x)
n, f, x = best
ys, xs = np.nonzero(np.abs(x) > 12)
print(d.name, "frames", len(fs), "changed px per frame", hit)
if n:
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    print(f"peak {f.name}: {n} px, bbox x {x0}-{x1} y {y0}-{y1}, mean diff {x[np.abs(x) > 12].mean():+.1f}")
    im = Image.open(f).convert("RGB")
    im.save(out + "-full.jpg", quality=90)
    pad = 60
    box = (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))
    c = im.crop(box)
    s = max(1, min(6, 900 // max(c.size)))
    c = c.resize((c.width * s, c.height * s), Image.NEAREST)
    arr = np.asarray(c, np.float32)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    Image.fromarray(np.clip((arr - lo) / max(hi - lo, 1) * 255, 0, 255).astype("uint8")).save(out + "-crop.png")
