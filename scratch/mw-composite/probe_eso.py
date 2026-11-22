#!/usr/bin/env python3
"""Which projection is ESO's eso0932a (S. Brunier, CC BY 4.0)? Corner coverage, then the brightest blob
near each bright star's predicted position under plate carree, Aitoff and Hammer (galactic, l=0 centre,
l increasing to the LEFT)."""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
a = np.asarray(Image.open("/home/peter/tmp/mwcomp/dl/eso0932a.jpg").convert("L")).astype(np.float32); Hh, Ww = a.shape
print("size", Ww, Hh, "corner means", [round(float(a[:100, :100].mean()), 1), round(float(a[:100, -100:].mean()), 1), round(float(a[Hh//2-50:Hh//2+50, :60].mean()), 1)])
row = a[Hh // 2]; nz = np.where(row > 8)[0]; col = a[:, Ww // 2]; nzc = np.where(col > 8)[0]
print("mid-row lit span", nz.min(), nz.max(), " mid-col lit span", nzc.min(), nzc.max())
top = a[150]; nzt = np.where(top > 8)[0]; print("row 150 lit span", (nzt.min(), nzt.max()) if nzt.size else None)
def pc(l, b): L = ((l + 180) % 360) - 180; return Ww / 2 - L / 180 * Ww / 2, Hh / 2 - b / 90 * Hh / 2
def aitoff(l, b):
    L = np.radians(((l + 180) % 360) - 180); B = np.radians(b); al = np.arccos(np.cos(B) * np.cos(L / 2)); s = np.sinc(al / np.pi)
    x = 2 * np.cos(B) * np.sin(L / 2) / s; y = np.sin(B) / s; return Ww / 2 - x / np.pi * Ww / 2, Hh / 2 - y / (np.pi / 2) * Hh / 2
def hammer(l, b):
    L = np.radians(((l + 180) % 360) - 180); B = np.radians(b); d = np.sqrt(1 + np.cos(B) * np.cos(L / 2))
    x = 2 * np.sqrt(2) * np.cos(B) * np.sin(L / 2) / d; y = np.sqrt(2) * np.sin(B) / d
    return Ww / 2 - x / (2 * np.sqrt(2)) * Ww / 2, Hh / 2 - y / np.sqrt(2) * Hh / 2
STARS = {"Sirius": (227.23, -8.89), "Canopus": (261.21, -25.29), "Arcturus": (15.06, 69.11), "Vega": (67.45, 19.24),
         "Capella": (162.59, 4.57), "Rigel": (209.24, -25.25), "Betelgeuse": (199.79, -8.96), "Antares": (351.95, 15.06),
         "Spica": (316.11, 50.84), "Deneb": (84.28, 1.99), "Altair": (47.74, -8.91), "Achernar": (290.84, -58.79)}
s = ndi.gaussian_filter(a, 2)
for name, f in (("platecarree", pc), ("aitoff", aitoff), ("hammer", hammer)):
    errs = []
    for st, (l, b) in STARS.items():
        x, y = f(l, b); x, y = int(round(float(x))), int(round(float(y))); R = 60
        sub = s[max(y - R, 0):y + R, max(x - R, 0):x + R]
        if sub.size == 0: continue
        yy, xx = np.unravel_index(np.argmax(sub), sub.shape); errs.append(np.hypot(xx - min(R, x), yy - min(R, y)))
    print(f"{name:12s} median offset of brightest blob from predicted bright star: {np.median(errs):5.1f} px  ({np.round(errs).astype(int).tolist()})")
