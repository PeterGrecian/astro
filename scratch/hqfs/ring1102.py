#!/usr/bin/env python3
"""hqfs night of 2026-11-02, focus at 7.09 mm: how wide are the star rings?
Median of a run of frames removes the fixed pattern; then, for the brightest stars in
several frames, the radial profile gives the ring's peak radius and its outer half-max
diameter. Sizes printed in superpixels (1014x760) and raw px (2028x1520, as Peter's probes)."""
import glob, os, sys
os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

NIGHT = "/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-02"
A, B = int(sys.argv[1]) if len(sys.argv) > 1 else 849, int(sys.argv[2]) if len(sys.argv) > 2 else 902
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{NIGHT}/*/*.fits.fz")}
ns = [n for n in range(A, B + 1) if n in fs]

def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32)
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4

cube = np.array([load(n) for n in ns])
fixed = np.median(cube, axis=0)
R = 60
yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
rr = np.hypot(yy, xx)

def profile(cut):
    rb = np.round(rr).astype(int)
    return np.bincount(rb.ravel(), cut.ravel()) / np.bincount(rb.ravel())

res = []
for k in range(0, len(ns), max(1, len(ns) // 6)):
    d = cube[k] - fixed
    d -= np.median(d)
    s = ndi.gaussian_filter(d, 3)
    sig = 1.4826 * np.median(np.abs(s))
    lab, n = ndi.label(s > 8 * sig)
    if n == 0:
        continue
    flux = ndi.sum(d, lab, range(1, n + 1))
    com = np.array(ndi.center_of_mass(np.clip(d, 0, None), lab, range(1, n + 1)))
    for i in np.argsort(-flux)[:8]:
        cy, cx = com[i]
        y0, x0 = int(round(cy)), int(round(cx))
        if not (R < y0 < d.shape[0] - R and R < x0 < d.shape[1] - R):
            continue
        cut = d[y0 - R:y0 + R + 1, x0 - R:x0 + R + 1]
        # re-centre on the ring's centre of light
        my, mx = ndi.center_of_mass(np.clip(cut, 0, None))
        cut = ndi.shift(cut, (R - my, R - mx), order=1)
        p = profile(cut)[:R]
        bg = np.median(p[-10:])
        p = p - bg
        pk = int(np.argmax(p))
        half = p[pk] / 2
        out = pk + np.argmax(p[pk:] < half) if (p[pk:] < half).any() else R
        # interpolate the half-max crossing
        if out > pk and out < R:
            r_out = out - 1 + (p[out - 1] - half) / (p[out - 1] - p[out])
        else:
            r_out = np.nan
        dip = p[0] / p[pk] if p[pk] > 0 else np.nan
        res.append((ns[k], cx, cy, flux[i], pk, r_out, dip, p[pk]))

res = np.array(res)
print(f"frames {A}-{B}: {len(ns)} loaded, {len(res)} star measurements")
print(" frame     x      y      flux  peak_r  outer_hm_r  centre/peak  peak_adu")
for r in res:
    print(f"{int(r[0]):6d} {r[1]:6.1f} {r[2]:6.1f} {r[3]:9.0f} {r[4]:6.0f} {r[5]:10.1f} {r[6]:11.2f} {r[7]:9.1f}")
good = res[np.isfinite(res[:, 5])]
D = 2 * good[:, 5]
print(f"\nouter half-max diameter: median {np.median(D):.1f} superpixels = {2*np.median(D):.1f} raw px "
      f"(p25 {np.percentile(D,25):.1f}, p75 {np.percentile(D,75):.1f} sp); ring peak radius median {np.median(good[:,4]):.0f} sp")
print(f"centre/peak median {np.nanmedian(good[:,6]):.2f}  (<1 means a hollow ring)")
