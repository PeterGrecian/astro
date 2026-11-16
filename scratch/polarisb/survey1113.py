#!/usr/bin/env python3
"""Polaris B, hqfs night 2026-11-13: where is Polaris A in each frame? Raw (Bayer) frame,
brightest blob centroid, saturated px count, by exposure. Prints a table to stdout."""
import glob, os, csv
os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-11-13"
rows = list(csv.DictReader(open(f"{NIGHT}/brightness.csv")))
print("rows", len(rows))
with fits.open(rows[100]["filename"]) as h:
    hd = h[1].header; a = h[1].data
print("shape", a.shape, a.dtype, {k: hd.get(k) for k in ("EXPTIME","GAIN","ANALOGUE","BINNING","XBINNING","DATE-OBS","FOCUSPOS","BITPIX")})
print([k for k in hd.keys()][:80])
step = 25
for i, r in enumerate(rows[::step]):
    f = r["filename"]
    with fits.open(f) as h:
        a = h[1].data.astype(np.float32); t = h[1].header.get("DATE-OBS","")[11:19]
    s = ndi.gaussian_filter(a, 3)
    y, x = np.unravel_index(np.argmax(s), s.shape)
    sat = int((a >= a.max() * 0.98).sum()) if a.max() >= 4000 else 0
    print(f"{f.split('-')[-1][:5]} {t} exp {float(r['exptime']):8.4f} x {x:5d} y {y:5d} peak {a.max():6.0f} med {np.median(a):6.0f} sat {sat}", flush=True)
