#!/usr/bin/env python3
"""Streak length of bright stars: HQ16 detrans stack vs its first sub.
Length = extent along the drift direction (20.8 deg) of pixels above half the
star's peak (above local background). Run on muppet from ~/astro."""
import glob, os, numpy as np
from PIL import Image
from astropy.io import fits
T = os.path.expanduser("~/tmp/mw-1112")
st = np.asarray(Image.open(f"{T}/hq16-O.png").convert("L"), np.float32)
f0 = sorted(glob.glob(f"{T}/hq16-winO/*.fits.fz"))[0]
d = fits.getdata(f0).astype(np.float32)
if d.max() > 4096: d /= 16
one = d[0::2, 0::2] + d[0::2, 1::2] + d[1::2, 0::2] + d[1::2, 1::2]
th = np.radians(20.8); u = np.array([np.cos(th), np.sin(th)])


def stars(a, n=12):
    from scipy.ndimage import maximum_filter, median_filter
    bg = median_filter(a[::4, ::4], 15).repeat(4, 0).repeat(4, 1)[:a.shape[0], :a.shape[1]]
    s = a - bg
    pk = (s == maximum_filter(s, 61)) & (s > 0)
    ys, xs = np.nonzero(pk); v = s[ys, xs]; o = np.argsort(-v)
    out = []
    for i in o:
        y, x = ys[i], xs[i]
        if 60 < y < a.shape[0] - 60 and 60 < x < 1500 and a[y, x] < 0.9 * a.max():
            out.append((x, y)); 
        if len(out) == n: break
    return s, out


def length(s, x, y):
    w = s[y - 50:y + 51, x - 50:x + 51]; w = w - np.median(w)
    from scipy.ndimage import label
    lab, _ = label(w > 0.5 * w.max()); m = lab == lab[50, 50]
    yy, xx = np.nonzero(m); p = (xx - 50) * u[0] + (yy - 50) * u[1]; q = -(xx - 50) * u[1] + (yy - 50) * u[0]
    return p.max() - p.min() + 1, q.max() - q.min() + 1, w.max()


for name, a in (("first sub", one), ("18-min stack", st)):
    s, pts = stars(a)
    L = [length(s, x, y) for x, y in pts]
    print(f"{name:13s} along-drift {np.median([l[0] for l in L]):5.1f} px  across {np.median([l[1] for l in L]):4.1f} px  "
          f"(each: {[int(l[0]) for l in L]})")
