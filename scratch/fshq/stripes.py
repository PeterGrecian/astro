#!/usr/bin/env python3
"""Stripes in fshq night frames: size of row and column banding against pixel noise, fixed or changing frame to frame."""
import glob
import numpy as np
from astropy.io import fits

D = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30/18"
def load(n):
    with fits.open(f"{D}/20261030T174011Z-{n:05d}.fits.fz") as h:
        return h[1].data.astype(np.float32), h[1].header
a, hdr = load(1001)
print({k: hdr[k] for k in ("GAIN", "EXPTIME") if k in hdr})
print("pedestal values, 5 lowest/most common:", np.unique(a[::7, ::7].astype(int), return_counts=True)[0][:12])
vals, cnt = np.unique(a.astype(int), return_counts=True)
top = np.argsort(-cnt)[:8]
print("most common ADU:", sorted(zip(vals[top].tolist(), cnt[top].tolist())))
print("mean", a.mean(), "median", np.median(a), "pixel std (clipped)", np.std(a[(a > 240) & (a < 285)]))
frames = [load(n)[0] for n in range(1001, 1009)]
for name, ax in (("rows", 1), ("columns", 0)):
    prof = np.array([np.median(f, axis=ax) if False else f.mean(axis=ax) for f in frames])
    # a star adds little to a whole-line mean, so use it as is
    mean_prof = prof.mean(axis=0)
    fixed = np.std(mean_prof - np.convolve(mean_prof, np.ones(51) / 51, "same"))
    change = np.std(prof - mean_prof)
    print(f"{name}: fixed banding {fixed:.3f} ADU, changing frame to frame {change:.3f} ADU")
    d = prof[0] - prof[0].mean()
    f = np.abs(np.fft.rfft(d - np.convolve(d, np.ones(51) / 51, "same")))
    k = np.argsort(-f[2:])[:3] + 2
    print("   strongest periods (lines):", [round(len(d) / int(i), 1) for i in k])
# by CFA channel: a pattern of 2 lines may just be the Bayer colours
for nm, c in (("R", a[0::2, 0::2]), ("G1", a[0::2, 1::2]), ("G2", a[1::2, 0::2]), ("B", a[1::2, 1::2])):
    print(nm, "median", np.median(c), "std", round(float(np.std(c[(c > 240) & (c < 285)])), 2))
diff = frames[0] - frames[1]
d = diff[(np.abs(diff) < 25)]
print("noise from two-frame difference /sqrt2:", round(float(d.std() / 2 ** .5), 2))
print("row-mean std of difference /sqrt2:", round(float(diff.mean(axis=1).std() / 2 ** .5), 3), " expected from pixel noise alone:", round(float(d.std() / 2 ** .5 / 2028 ** .5), 3))
print("col-mean std of difference /sqrt2:", round(float(diff.mean(axis=0).std() / 2 ** .5), 3), " expected from pixel noise alone:", round(float(d.std() / 2 ** .5 / 1520 ** .5), 3))
