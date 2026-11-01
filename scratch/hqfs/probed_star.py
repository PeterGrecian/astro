#!/usr/bin/env python3
"""The star Peter probed in frame 01001: size of the defocus ring, raw levels, and the trail from neighbouring frames."""
import glob
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

D = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30/18"
def load(n):
    with fits.open(f"{D}/20261030T174011Z-{n:05d}.fits.fz") as h:
        return h[1].data.astype(np.float32)
raw = load(1001)
ref = np.median([load(n) for n in (981, 991, 1011, 1021)], axis=0)
d = raw - ref
cx, cy, R = 635, 1131, 90
c = d[cy - R:cy + R, cx - R:cx + R]
print("raw max in box", raw[cy - R:cy + R, cx - R:cx + R].max(), "n>=4090", (raw[cy - R:cy + R, cx - R:cx + R] >= 4090).sum(), "frame median", np.median(raw))
for name, a in (("R", c[0::2, 0::2]), ("G", (c[0::2, 1::2] + c[1::2, 0::2]) / 2), ("B", c[1::2, 1::2])):
    print(name, "peak", round(float(a.max()), 1), "sum>3sig", round(float(a[a > 3 * 1.48 * np.median(np.abs(a))].sum())))
s = ndi.gaussian_filter(c, 1.5)
sig = 1.4826 * np.median(np.abs(s))
m = s > 5 * sig
lab, n = ndi.label(m)
sz = ndi.sum(m, lab, range(1, n + 1))
big = lab == (np.argmax(sz) + 1)
ys, xs = np.nonzero(big)
print("largest blob px", big.sum(), "x", xs.min() + cx - R, xs.max() + cx - R, "y", ys.min() + cy - R, ys.max() + cy - R, "extent", np.ptp(xs) + 1, np.ptp(ys) + 1)
# ring profile about the flux centroid, and width in 8 directions: drift lengthens one axis only
my, mx = ndi.center_of_mass(np.clip(c, 0, None) * big)
print("centroid", round(mx + cx - R, 1), round(my + cy - R, 1))
yy, xx = np.mgrid[:c.shape[0], :c.shape[1]]
r = np.hypot(xx - mx, yy - my)
print("radial mean:", " ".join(f"{int(a)}:{s[(r >= a) & (r < a + 5)].mean():.0f}" for a in range(0, 80, 5)))
for ang in range(0, 180, 30):
    t = np.radians(ang)
    pts = np.arange(-85, 86)
    v = ndi.map_coordinates(s, [my + pts * np.sin(t), mx + pts * np.cos(t)], order=1)
    above = pts[v > 0.25 * v.max()]
    print(f"angle {ang:3d}: outer edge to edge {above.max() - above.min():3d} px, peak {v.max():.0f}")
ramp = " .:-=+*#%@"
b = ndi.zoom(np.clip(s, 0, None), 0.33, order=1)
b = b / b.max()
print("\n".join("".join(ramp[int(min(v, 1) * 9)] for v in row) for row in b))
# drift of this star across neighbouring frames
pos = []
for n in range(993, 1010):
    e = load(n) - ref
    q = ndi.gaussian_filter(e[cy - 200:cy + 200, cx - 300:cx + 300], 4)
    py, px = np.unravel_index(q.argmax(), q.shape)
    pos.append((n, px + cx - 300, py + cy - 200, round(float(q.max()), 1)))
print(pos)
