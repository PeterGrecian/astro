#!/usr/bin/env python3
"""Named stars in the still: aperture flux at the catalogue position against the time each star crossed the field."""
import csv, os
os.environ["OMP_NUM_THREADS"] = "1"
os.nice(15)
import numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.io import fits
from astropy.wcs import WCS
from scipy import ndimage as ndi

OUT = os.path.expanduser("~/tmp/fshq-survey")
img = np.load(f"{OUT}/night_still_raw_v2.npy"); fr = np.load(f"{OUT}/night_still_frames_v2.npy")
raw = img.mean(axis=0)
w = WCS(fits.getheader(f"{OUT}/solve/stars.xy.wcs"))
rows = [x for x in csv.DictReader(open(f"{OUT}/hyg.csv")) if x["dec"] and float(x["dec"]) > 84 and float(x["mag"]) < 9.3]
ra = np.array([float(x["ra"]) * 15 for x in rows]); dec = np.array([float(x["dec"]) for x in rows]); mag = np.array([float(x["mag"]) for x in rows])
p = w.all_world2pix(np.c_[ra, dec], 0)
H, W = raw.shape
yy, xx = np.mgrid[:H, :W]
POLE = np.array([1000.8, 1000.8])
PER = np.radians(15.0411 * 3 / 3600)
out = []
for j in np.argsort(mag):
    x, y = p[j]
    if not (16 <= x < W - 16 and 16 <= y < H - 16) or fr[int(y), int(x)] < 60:
        continue
    d = np.hypot(xx - x, yy - y)
    ap = d <= 14
    ann = (d > 18) & (d <= 28) & (fr >= 60)
    if ann.sum() < 50:
        continue
    f = float((raw[ap] - np.median(raw[ann])).sum())
    noise = 1.4826 * np.median(np.abs(raw[ann] - np.median(raw[ann]))) * ap.sum() ** .5
    phi = np.arctan2(x - POLE[0], POLE[1] - y)        # clockwise from straight up
    n = 7449 + phi / PER
    hrs = 17 + 40 / 60 + n * 3 / 3600
    out.append((hrs % 24, mag[j], f, f / max(noise, 1e-6), x, y, rows[j]))
out.sort(key=lambda t: (t[0] - 17) % 24)
print("crossing time GMT, mag, flux, S/N, zero-point relative (flux * 10^(0.4 mag)), x y, name")
zp = np.array([t[2] * 10 ** (0.4 * t[1]) for t in out if t[3] > 5])
ref = np.median(zp)
for h, m, f, sn, x, y, r in out:
    nm = " ".join(t.strip() for t in (r.get("proper", ""), r.get("bf", "")) if t.strip())
    print(f"{int(h):02d}:{int(h % 1 * 60):02d} {m:5.2f} {f:8.1f} {sn:6.1f} {f * 10 ** (0.4 * m) / ref:7.2f} {x:5.0f} {y:5.0f} {nm or '-'} HIP{r['hip']} HD{r['hd']}")
