#!/usr/bin/env python3
"""Per-frame centroid and size of the changed region in plane_catch events.

    catch_track.py EVENT_DIR...
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

for d in map(Path, sys.argv[1:]):
    fs = sorted(d.glob("*.jpg"))
    bg = np.median([np.asarray(Image.open(f).convert("L"), np.float32) for f in fs[:5]], axis=0)
    print(d.name)
    for f in fs:
        x = np.asarray(Image.open(f).convert("L"), np.float32) - bg
        ys, xs = np.nonzero(np.abs(x) > 12)
        if len(xs) > 20:
            print(f"  {f.stem} n {len(xs):6d} centre ({xs.mean():6.0f},{ys.mean():6.0f}) "
                  f"x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()} diff {x[np.abs(x) > 12].mean():+.1f}")
