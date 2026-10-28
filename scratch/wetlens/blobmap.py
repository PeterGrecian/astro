"""Ratio of each night's sum image to a reference night, binned to a coarse grid, to find a local blob."""
import os, sys, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
root = os.environ["BIGSTORE"] + "/astrocam-frames"
def img(n, name):
    with fits.open(f"{root}/{n}/{name}") as h:
        for x in h:
            if x.data is not None: d = x.data.astype(np.float64); break
    if d.ndim == 3: d = d.mean(axis=0) if d.shape[0] <= 4 else d.mean(axis=2)
    return d
def grid(d, gy=12, gx=24):
    H, W = d.shape; d = d[:H//gy*gy, :W//gx*gx]
    return np.median(d.reshape(gy, H//gy, gx, W//gx).transpose(0, 2, 1, 3).reshape(gy, gx, -1), axis=2)
name = sys.argv[1]; ref = sys.argv[2]; nights = sys.argv[3:]
R = grid(img(ref, name))
for n in nights:
    g = grid(img(n, name)) / R; g /= np.median(g)
    print(f"== {n} / {ref} ({name})  row 0 = FITS row 0")
    for row in g: print(" ".join(f"{v:5.2f}" for v in row))
