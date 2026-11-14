#!/usr/bin/env python3
"""Why are stars sky blue in colour.jpg? Per-stage values at catalogue stars."""
import os, json, warnings
import numpy as np
from importlib.machinery import SourceFileLoader
from pathlib import Path
from datetime import datetime, timezone
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u
from PIL import Image
from scipy.ndimage import gaussian_filter
warnings.filterwarnings("ignore")
os.environ.setdefault("DEROT_CAMERA", "eclipticam-v3w")
an = SourceFileLoader("an", str(Path.home() / "astro/bin/derot-annotate")).load_module(); ds = an.ds
T = Path.home() / "tmp/mw-1112"
cm = ds.CameraModel(str(an.night_dir("2026-11-12") / "skyglow-cammodel.json"))
t = datetime(2026, 11, 13, 4, 0, tzinfo=timezone.utc)
S = {"Betelgeuse": (88.79, 7.41), "Rigel": (78.63, -8.20), "Bellatrix": (81.28, 6.35), "Procyon": (114.83, 5.23),
     "Alhena": (99.43, 16.40), "Mintaka": (83.00, -0.30), "Sirius": (101.29, -16.72), "Aldebaran": (68.98, 16.51)}
x, y, ok = an.project(cm, SkyCoord([v[0] for v in S.values()] * u.deg, [v[1] for v in S.values()] * u.deg), t)
raw = {c: np.nan_to_num(fits.getdata(T / f"stack-{c}/derot-sky.fits", 0)) for c in "RGB"}
L = np.nan_to_num(fits.getdata(T / "stack/derot-sky.fits", 0))
im = np.asarray(Image.open(T / "figs/colour.jpg"))
CROP = (700, 330)
print("star        stackpeak R G B (sum L)      jpg RGB at star (max in 5x5)")
for (nm, xi, yi) in zip(S, x, y):
    xi, yi = int(round(xi)), int(round(yi))
    if not (5 < xi < 2299 and 5 < yi < 1290):
        continue
    pk = [raw[c][yi - 3:yi + 4, xi - 3:xi + 4].max() for c in "RGB"]
    jx, jy = xi - CROP[0], yi - CROP[1]
    j = im[jy - 2:jy + 3, jx - 2:jx + 3].reshape(-1, 3) if 2 < jx < im.shape[1] - 3 and 2 < jy < im.shape[0] - 3 else None
    js = j[j.sum(1).argmax()] if j is not None else "-"
    print(f"{nm:11s} {pk[0]:7.1f} {pk[1]:7.1f} {pk[2]:7.1f} ({L[yi-3:yi+4, xi-3:xi+4].max():7.1f})   {js}")
# overall: how many star-ish pixels are blue-dominant
a = im.astype(int); bright = a.sum(2) > 300
print("bright px", bright.sum(), " B>R+40:", ((a[..., 2] > a[..., 0] + 40) & bright).sum(), " R>B+40:", ((a[..., 0] > a[..., 2] + 40) & bright).sum())
print("median of bright px RGB", np.median(a[bright], axis=0))
