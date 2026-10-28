"""Coarse-grid ratio of early frames to a mid-night reference, to catch a blob that dries out."""
import os, glob, numpy as np
from astropy.io import fits
root = os.environ["BIGSTORE"] + "/astrocam-frames/2026-10-27"
def load(p):
    with fits.open(p) as h:
        for x in h:
            if x.data is not None: d = x.data.astype(np.float64); break
    return d.mean(axis=0) if d.ndim == 3 and d.shape[0] <= 4 else d
def grid(d, gy=9, gx=16):
    H, W = d.shape; d = d[:H//gy*gy, :W//gx*gx]
    return np.median(d.reshape(gy, H//gy, gx, W//gx).transpose(0, 2, 1, 3).reshape(gy, gx, -1), axis=2)
fs = sorted(glob.glob(f"{root}/??/*.fits.fz"), key=os.path.basename)
ref = np.median([grid(load(p)) for p in fs[1400:1460:6]], axis=0)
for i in (0, 20, 60, 120, 240):
    g = grid(load(fs[i])) / ref; g /= np.median(g)
    print(f"== frame {i} {os.path.basename(fs[i])}  / mid-night ref (row 0 = FITS row 0)")
    for row in g: print(" ".join(f"{v:5.2f}" for v in row))
