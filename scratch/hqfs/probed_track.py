#!/usr/bin/env python3
"""Follow the probed star: drift rate, how long it stays in the field, and a drift-aligned stack of its defocus image."""
import glob, os
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from PIL import Image

N = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{N}/*/*.fits.fz")}
def load(n):
    with fits.open(fs[n]) as h:
        return h[1].data.astype(np.float32)
ref = np.median([load(n) for n in range(100, 14000, 700)], axis=0)
OUT = os.path.expanduser("~/tmp/fshq-survey"); os.makedirs(OUT, exist_ok=True)

print("night track: frame, UTC-ish minutes from start, brightest blob x y, smoothed peak, frame median")
for n in list(range(1, 14896, 300)):
    e = load(n) - ref
    q = ndi.gaussian_filter(e, 8)
    y, x = np.unravel_index(q.argmax(), q.shape)
    print(n, round(n * 3 / 60), x, y, round(float(q.max()), 2), round(float(np.median(e)), 1), flush=True)

print("short track around 1001")
pos = {}
for n in range(981, 1022, 4):
    e = load(n) - ref
    q = ndi.gaussian_filter(e[900:1400, 300:1000], 8)
    y, x = np.unravel_index(q.argmax(), q.shape)
    pos[n] = (x + 300, y + 900)
    print(n, x + 300, y + 900, round(float(q.max()), 2))
ns = sorted(pos)
xs = np.array([pos[n][0] for n in ns], float); ys = np.array([pos[n][1] for n in ns], float)
vx, x0 = np.polyfit(ns, xs, 1); vy, y0 = np.polyfit(ns, ys, 1)
print(f"drift per frame dx {vx:.2f} dy {vy:.2f} binned px, {np.hypot(vx, vy):.2f} px/frame, {np.hypot(vx, vy) * 2.13 / 3:.2f} arcsec/s")

stack = np.zeros((241, 241), np.float32)
for n in range(961, 1042):
    e = load(n) - ref
    x, y = int(round(vx * n + x0)), int(round(vy * n + y0))
    c = e[y - 120:y + 121, x - 120:x + 121]
    if c.shape == stack.shape:
        stack += c
stack /= 81
s = ndi.gaussian_filter(stack, 1)
sig = 1.4826 * np.median(np.abs(s))
print("stack peak", round(float(s.max()), 2), "sigma", round(float(sig), 3))
for frac in (0.1, 0.25):
    ys_, xs_ = np.nonzero(s > frac * s.max())
    print(f">{frac:.0%} of peak: x extent {np.ptp(xs_) + 1} y extent {np.ptp(ys_) + 1}")
for ang in range(0, 180, 30):
    t = np.radians(ang)
    pts = np.arange(-115, 116)
    v = ndi.map_coordinates(s, [120 + pts * np.sin(t), 120 + pts * np.cos(t)], order=1)
    a = pts[v > 0.2 * s.max()]
    print(f"angle {ang:3d}: {a.max() - a.min() if len(a) else 0} px")
Image.fromarray((255 * np.clip(s / s.max(), 0, 1) ** 0.6).astype(np.uint8)).resize((723, 723), Image.BICUBIC).save(f"{OUT}/probed_stack.png")
ramp = " .:-=+*#%@"
b = ndi.zoom(np.clip(s, 0, None), 0.25, order=1); b /= b.max()
print("\n".join("".join(ramp[int(min(v, 1) * 9)] for v in r) for r in b))
