#!/usr/bin/env python3
"""hqfs 2026-11-06: one bright star in single frames through the night (fixed pattern
removed by a local median), against the stacked star-crops sheet. Tiles 81 superpixels
(about 6.2 arcmin) across, each stretched to its own peak; scale bar 1 arcmin."""
import glob, os
os.nice(10)
import numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
NIGHT = "/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-06"
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{NIGHT}/*/*.fits.fz")}
# (frame, approx x, y in superpixels) from shapes1106.py: star C 22:48-00:38, star D 18:43-19:28
PICKS = [(376, 196, 270), (451, 172, 372), (526, 154, 475), (601, 163, 83), (1601, 496, 44), (1676, 457, 128),
         (1751, 424, 212), (1826, 396, 299), (1876, 382, 358), (1926, 369, 418), (2001, 355, 509), (2051, 350, 570)]
R, S, ARC = 40, 3, 4.57
def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32); t = h[1].header.get("DATE-OBS", "")
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4, t[11:16]
tiles = []
for n, x, y in PICKS:
    fixed = np.median([load(m)[0] for m in range(n - 10, n + 11, 2) if m in fs and m != n], axis=0)
    a, t = load(n); d = a - fixed
    c = d[y - R:y + R + 1, x - R:x + R + 1]
    my, mx = ndi.center_of_mass(np.clip(ndi.gaussian_filter(c, 2), 0, None))
    y, x = y + int(round(my - R)), x + int(round(mx - R))
    c = d[y - R:y + R + 1, x - R:x + R + 1]; c = c - np.median(c)
    v = np.clip(c / np.percentile(c, 99.8), 0, 1) ** 0.6
    im = Image.fromarray((v * 255).astype(np.uint8)).resize(((2 * R + 1) * S,) * 2, Image.NEAREST).convert("RGB")
    dr = ImageDraw.Draw(im); dr.text((4, 4), f"{t} UTC  ({x},{y})", fill=(255, 200, 0))
    bar = 60 / ARC * S; dr.line([(6, im.height - 10), (6 + bar, im.height - 10)], fill=(255, 255, 255), width=3)
    dr.text((10 + bar, im.height - 18), "1'", fill=(255, 255, 255))
    tiles.append(im)
W = tiles[0].width
sheet = Image.new("RGB", (6 * W, 2 * W + 24))
for i, im in enumerate(tiles): sheet.paste(im, ((i % 6) * W, (i // 6) * W))
ImageDraw.Draw(sheet).text((6, 2 * W + 6), "hqfs 2026-11-06 single 12 s frames, local median removed. Top: star D 18:43-19:28. Bottom: star C 22:48-00:18. Bar = 1 arcmin (4.57\"/superpixel).", fill=(220, 220, 220))
out = os.path.expanduser("~/tmp/hqfs1106-onestar.png"); sheet.save(out); print(out)
