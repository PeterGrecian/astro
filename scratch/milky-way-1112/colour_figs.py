#!/usr/bin/env python3
"""Colour version of the v3w winter Milky Way stack (night 2026-11-12, 03:40-04:20 UTC).

Inputs on muppet, ~/tmp/mw-1112/: stack/ (sum) and stack-{R,G,B}/ from
`derot-sky stack --channel` (all on the 2x2-sum scale, glow subtracted).
LRGB: brightness from the low-noise sum stack, colour from R, G, B smoothed (3.5 px Gaussian: one colour per star, not
the red and blue halos the lens gives each; B is also 5x noisier than G).
White balance from ~70 catalogue stars (wb_fit.py, writes wb.json): R/G and
B/G fitted against Hipparcos B-V and set neutral at B-V 0.62, the Sun's colour.
Writes figs/colour.jpg (same crop as deep.jpg) and figs/colour-orion.jpg
(1:1 crop around Orion), privacy-cropped, with a scale bar.
"""
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
import numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

os.environ.setdefault("DEROT_CAMERA", "eclipticam-v3w")
an = SourceFileLoader("an", str(Path.home() / "astro/bin/derot-annotate")).load_module()
ds = an.ds
T = Path.home() / "tmp/mw-1112"; OUT = T / "figs"
cm = ds.CameraModel(str(an.night_dir("2026-11-12") / "skyglow-cammodel.json"))
H = an.privacy_keep(1296)
CROP = (700, 330, 1820, 1060)

# white balance from ~70 Hipparcos stars (V<5) in the stacks themselves: wb_fit.py
# fits R/G and B/G against catalogue B-V and makes B-V 0.62 (the Sun) neutral
import json
_w = json.load(open(T / "wb.json"))
wb = np.array([_w["R"], 1.0, _w["B"]])
print(f"white balance R x{wb[0]:.2f} G x1 B x{wb[2]:.2f} (Sun-coloured star neutral)")

L = np.nan_to_num(fits.getdata(T / "stack/derot-sky.fits", 0))
wt = fits.getdata(T / "stack/derot-sky.fits", 1)
from scipy.ndimage import median_filter


def chan(c):
    """One colour stack, its own local background removed (a 41 px median on a
    4x-decimated copy, so each channel's residual glow cannot tint the stars),
    then smoothed so each star gets one colour."""
    a = np.nan_to_num(fits.getdata(T / f"stack-{c}/derot-sky.fits", 0))
    bg = median_filter(a[::4, ::4], 11).repeat(4, 0).repeat(4, 1)[:a.shape[0], :a.shape[1]]
    return gaussian_filter(a - bg, 3.5)


C = np.dstack([chan(c) * w for c, w in zip("RGB", wb)])
good = wt > 0.6 * wt.max()
lo, hi = np.percentile(L[good], 20), np.percentile(L[good], 99.9)
x = np.clip((L - lo) / (hi - lo), 0, None)
Ls = np.arcsinh(10 * x) / np.arcsinh(10)                       # stretched brightness, as deep.jpg
# chroma: colour ratios only where the sum stack has real signal (> 3 sigma,
# full colour by 10 sigma); background left grey so B's noise cannot tint it
Cs = C
tot = Cs.sum(2, keepdims=True)
ratio = np.where(tot > 0, Cs / np.maximum(tot, 1e-6) * 3, 1.0)
ratio = np.clip(ratio, 0.4, 1.8)
noise = 1.4826 * np.median(np.abs(L[good] - np.median(L[good])))
wcol = np.clip((L - np.median(L[good]) - 3 * noise) / (7 * noise), 0, 1)[..., None]
ratio = 1 + (ratio - 1) * wcol
rgb = np.clip(Ls[..., None] * ratio, 0, 1)
img = Image.fromarray((rgb[:H] * 255).astype(np.uint8))

try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 22)
except OSError:
    FONT = ImageFont.load_default(size=22)


def bar(im, Lpx, label):
    d = ImageDraw.Draw(im); y0 = im.height - 40
    d.line([30, y0, 30 + Lpx, y0], fill=(224, 224, 224), width=3)
    for xx in (30, 30 + Lpx):
        d.line([xx, y0 - 8, xx, y0 + 8], fill=(224, 224, 224), width=3)
    d.text((30, y0 + 10), label, fill=(224, 224, 224), font=FONT)


a = img.crop(CROP); bar(a, cm.f * np.radians(10), "10°"); a.save(OUT / "colour.jpg", quality=92)
# Orion close-up at 2x, so Betelgeuse and Rigel show their colour
from astropy.coordinates import SkyCoord
import astropy.units as u
from datetime import datetime, timezone
t = datetime(2026, 11, 13, 4, 0, tzinfo=timezone.utc)
names = {"Betelgeuse": (88.79, 7.41), "Rigel": (78.63, -8.20), "Bellatrix": (81.28, 6.35), "Saiph": (86.94, -9.67)}
xs, ys, _ = an.project(cm, SkyCoord([v[0] for v in names.values()] * u.deg, [v[1] for v in names.values()] * u.deg), t)
cx, cy = int(np.mean(xs)), int(np.mean(ys))
b = img.crop((cx - 200, cy - 220, cx + 200, cy + 220)).resize((800, 880), Image.LANCZOS)
d = ImageDraw.Draw(b)
for nm, xi, yi in zip(names, xs, ys):
    px, py = (xi - (cx - 200)) * 2, (yi - (cy - 220)) * 2
    d.text((px + 22, py - 12), nm, fill=(200, 200, 200), font=FONT)
bar(b, 2 * cm.f * np.radians(5), "5°"); b.save(OUT / "colour-orion.jpg", quality=92)
print("wrote", OUT / "colour.jpg", OUT / "colour-orion.jpg")

a = np.asarray(img).astype(int); br = a.sum(2) > 300
print("bright px", br.sum(), "B>R+40", ((a[..., 2] > a[..., 0] + 40) & br).sum(), "R>B+40", ((a[..., 0] > a[..., 2] + 40) & br).sum())
