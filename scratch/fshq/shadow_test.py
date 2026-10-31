#!/usr/bin/env python3
"""Where does the shadow by bright stars come from? Stack on one star in camera coordinates, three ways."""
import glob, os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "1"
os.nice(15)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

N = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{N}/*/*.fits.fz")}
NS = sorted(fs)[::100]
W = np.radians(15.0411 * 3 / 3600)
PX, PY = -502, -1763
SX, SY = 330.0, 560.0      # the probed star in superpixels at frame 1001

def green(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32)
    return (a[0::2, 1::2] + a[1::2, 0::2]) / 2

def level(a):
    med = np.median(a)
    k = np.abs(a - med) < 6
    return a[k].mean()

def bg(a):
    h, w = a.shape
    bh, bw = h // 64, w // 64
    b = a[:bh * 64, :bw * 64].reshape(bh, 64, bw, 64).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    med = np.median(b, axis=2, keepdims=True)
    keep = np.abs(b - med) < 6
    return ndi.zoom((b * keep).sum(axis=2) / keep.sum(axis=2), (h / bh, w / bw), order=1)

cube = np.array([green(n) - level(green(n)) for n in NS[::3]])
ref = np.median(cube, axis=0)
far = cube[[i for i, n in enumerate(NS[::3]) if abs(n - 1500) > 1500]]
ref_far = np.median(far, axis=0)      # only frames with this star out of the field
del cube, far
print("ref minus ref without this star: max", round(float((ref - ref_far).max()), 2), "min", round(float((ref - ref_far).min()), 2))
R = 110
st = {k: np.zeros((2 * R + 1, 2 * R + 1), np.float32) for k in ("raw", "ref", "ref_far", "ref_bg", "ref_far_bg")}
used = 0
for n in range(650, 2350, 10):
    th = W * (n - 1001)
    c, s = np.cos(th), np.sin(th)
    dx, dy = SX - PX, SY - PY
    x = int(round(PX + c * dx + s * dy)); y = int(round(PY - s * dx + c * dy))
    if not (R <= x < 1014 - R and R <= y < 760 - R):
        continue
    a = green(n); a = a - level(a)
    box = lambda m: m[y - R:y + R + 1, x - R:x + R + 1]
    st["raw"] += box(a)
    r = a - ref; rf = a - ref_far
    st["ref"] += box(r); st["ref_far"] += box(rf)
    st["ref_bg"] += box(r - bg(r)); st["ref_far_bg"] += box(rf - bg(rf))
    used += 1
print("frames", used)
yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
rr = np.hypot(xx, yy)
ang = np.degrees(np.arctan2(-yy, xx)) % 360
sec = ((ang + 22.5) // 45).astype(int) % 8
names = ["right", "up-right", "up", "up-left", "left", "down-left", "down", "down-right"]
for k, v in st.items():
    v /= used
    # level from the outer part of the box, so all columns compare
    v -= np.median(v[rr > 90])
    print(k.ljust(11), "centre", round(float(np.mean(v[rr < 30])), 2), "| 30-60 px:", " ".join(f"{names[i]} {v[(rr > 30) & (rr <= 60) & (sec == i)].mean():+.2f}" for i in range(8)))
print("radial, ref_far_bg:", " ".join(f"{a}:{st['ref_far_bg'][(rr >= a) & (rr < a + 10)].mean():+.2f}" for a in range(0, 110, 10)))
print("radial, raw:       ", " ".join(f"{a}:{st['raw'][(rr >= a) & (rr < a + 10)].mean():+.2f}" for a in range(0, 110, 10)))
