#!/usr/bin/env python3
"""hqfs night of 2026-11-06: star size and shape through the night.
Every STEP-th frame: subtract a local median (fixed pattern), take the brightest stars,
and measure the outer half-max diameter (raw px, as Peter's probes), the hollowness
(centre/peak), and second-moment ellipticity and position angle. Prints one line per frame."""
import glob, os, sys
os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
NIGHT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-06"
STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 25
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{NIGHT}/*/*.fits.fz")}
def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32); t = h[1].header.get("DATE-OBS", "")
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4, t
R = 40
yy, xx = np.mgrid[-R:R + 1, -R:R + 1]; rr = np.hypot(yy, xx); rb = np.round(rr).astype(int)
cache = {}
def get(n):
    if n not in cache: cache[n] = load(n)
    return cache[n]
for n0 in range(min(fs), max(fs) + 1, STEP):
    near = [n for n in range(n0 - 10, n0 + 11, 2) if n in fs]
    if n0 not in fs or len(near) < 5: continue
    fixed = np.median([get(n)[0] for n in near], axis=0)
    a, t = get(n0)
    d = a - fixed; d -= np.median(d)
    s = ndi.gaussian_filter(d, 3); sig = 1.4826 * np.median(np.abs(s))
    lab, k = ndi.label(s > 8 * sig)
    out = []
    if k:
        flux = ndi.sum(d, lab, range(1, k + 1))
        com = ndi.center_of_mass(np.clip(d, 0, None), lab, range(1, k + 1))
        for i in np.argsort(-flux)[:6]:
            y0, x0 = map(int, np.round(com[i]))
            if not (R < y0 < d.shape[0] - R and R < x0 < d.shape[1] - R): continue
            cut = d[y0 - R:y0 + R + 1, x0 - R:x0 + R + 1]
            my, mx = ndi.center_of_mass(np.clip(cut, 0, None))
            cut = ndi.shift(cut, (R - my, R - mx), order=1)
            p = np.bincount(rb.ravel(), cut.ravel()) / np.bincount(rb.ravel()); p = p[:R] - np.median(p[R - 8:R])
            pk = int(np.argmax(p)); half = p[pk] / 2
            o = pk + int(np.argmax(p[pk:] < half)) if (p[pk:] < half).any() else R
            r_out = o - 1 + (p[o - 1] - half) / (p[o - 1] - p[o]) if pk < o < R else np.nan
            w = np.clip(cut, 0, None) * (rr < min(R, 1.5 * r_out + 4 if r_out == r_out else R))
            m = w.sum(); qxx = (w * xx**2).sum() / m; qyy = (w * yy**2).sum() / m; qxy = (w * xx * yy).sum() / m
            e = np.hypot(qxx - qyy, 2 * qxy) / (qxx + qyy); pa = 0.5 * np.degrees(np.arctan2(2 * qxy, qxx - qyy))
            out.append((flux[i], x0, y0, 4 * r_out, p[0] / p[pk], e, pa))
    if out:
        o = np.array(out)
        print(f"{n0:5d} {t[11:19]} n={k:3d} D50raw={np.nanmedian(o[:,3]):5.1f} hollow={np.median(o[:,4]):.2f} "
              f"ell={np.median(o[:,5]):.2f} pa={np.median(o[:,6]):+5.0f}  " +
              " ".join(f"({x:.0f},{y:.0f} D{D:.0f} e{e:.2f}/{pa:+.0f})" for _, x, y, D, h, e, pa in out[:4]), flush=True)
    else:
        print(f"{n0:5d} {t[11:19]} n={k:3d}", flush=True)
    for n in list(cache):
        if n < n0 - 12: del cache[n]
