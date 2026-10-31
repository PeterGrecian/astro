#!/usr/bin/env python3
"""10-minute test stack, fshq 2026-10-30: derotate about the celestial pole, compare with a plain stack."""
import glob, os
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from PIL import Image

N = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{N}/*/*.fits.fz")}
OUT = os.path.expanduser("~/tmp/fshq-survey"); os.makedirs(OUT, exist_ok=True)
FIRST, COUNT = 901, 200
W = np.radians(15.0411 * 3 / 3600)   # sidereal rotation per 3 s frame

def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32)
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4

ref = np.median([load(n) for n in range(100, 14000, 700)], axis=0)
frames = {n: load(n) - ref for n in range(FIRST, FIRST + COUNT)}
for n in frames:
    frames[n] -= np.median(frames[n])

def stack(px, py, ns):
    out = np.zeros_like(ref)
    t0 = FIRST + COUNT // 2
    for n in ns:
        th = W * (n - t0)
        c, s = np.cos(th), np.sin(th)
        M = np.array([[c, -s], [s, c]])
        p = np.array([py, px])
        out += ndi.affine_transform(frames[n], M, offset=p - M @ p, order=1, mode="constant")
    return out / len(ns)

def sharp(im):
    s = ndi.gaussian_filter(im, 1.5)
    return float((s[s > np.percentile(s, 99.5)] ** 2).sum())

best = (0, None)
for dx in range(-300, 301, 100):
    for dy in range(-300, 301, 100):
        px, py = -427 + dx, -1688 + dy
        v = sharp(stack(px, py, range(FIRST, FIRST + COUNT, 5)))
        if v > best[0]:
            best = (v, (px, py))
print("pole in superpixels, starting -427,-1688, best", best[1], flush=True)
px, py = best[1]
der = stack(px, py, range(FIRST, FIRST + COUNT))
plain = np.mean([frames[n] for n in frames], axis=0)
one = frames[FIRST + COUNT // 2]

def report(name, im):
    s = ndi.gaussian_filter(im, 1.5)
    sig = 1.4826 * np.median(np.abs(s[40:-40, 40:-40]))
    m = s > 6 * sig
    lab, n = ndi.label(m)
    sz = ndi.sum(m, lab, range(1, n + 1)) if n else np.array([])
    print(f"{name}: pixel noise {1.4826 * np.median(np.abs(im[40:-40, 40:-40])):.3f}, objects >6 sigma, 6+ px: {(sz >= 6).sum()}, peak {im.max():.1f}, smoothed peak {s.max():.2f}")
report("single frame", one); report("plain 200", plain); report("derotated 200", der)

def save(im, name, hi):
    Image.fromarray((255 * np.clip(im / hi, 0, 1) ** 0.5).astype(np.uint8)).save(f"{OUT}/{name}")
hi = np.percentile(ndi.gaussian_filter(der, 1), 99.95)
save(np.clip(der, 0, None), "stack10_derotated.png", hi)
save(np.clip(plain, 0, None), "stack10_plain.png", hi)

s = ndi.gaussian_filter(der, 2)
sig = 1.4826 * np.median(np.abs(s[40:-40, 40:-40]))
lab, n = ndi.label(s > 6 * sig)
objs = []
for j, sl in enumerate(ndi.find_objects(lab)):
    ysz, xsz = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    a = (lab[sl] == j + 1).sum()
    if a >= 6:
        objs.append((float((der[sl] * (lab[sl] == j + 1)).sum()), sl[1].start + xsz // 2, sl[0].start + ysz // 2, xsz, ysz, int(a)))
objs.sort(reverse=True)
print("flux x y (superpixels) width height area")
for o in objs[:15]:
    print(" ".join(f"{v:.0f}" for v in o))
ramp = " .:-=+*#%@"
if objs:
    _, x, y, *_ = objs[0]
    c = np.clip(ndi.gaussian_filter(der, 0.7)[max(y - 28, 0):y + 28, max(x - 28, 0):x + 28], 0, None)
    print("\n".join("".join(ramp[int(min(v / c.max(), 1) * 9)] for v in r) for r in c[::2]))
