#!/usr/bin/env python3
"""HQ16 figures for the winter Milky Way note (night 2026-11-12).

Inputs on muppet, ~/tmp/mw-1112/: hq16-O.png (detrans-sweep --mode deep,
20 subs 02:50-03:10 UTC, Orion) and hq16-A.png (04:10-04:30 UTC, Monoceros),
each plate-solved as solve/st{O,A}.wcs (astrometry.net, tycho2 indexes).
Detrans registers each window on its FIRST frame, so the WCS is that moment's.
Writes figs/hq16-{orion,monoceros}{,-labelled}.jpg, cropped to the part every
frame of the window covers (the shift is 0.375 px/s at 20.8 deg: ~380 px right
and ~145 px down over 18 min), with a 5 deg bar, turned 180 deg so north is near the top.
"""
from pathlib import Path
import warnings
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from astropy.wcs import WCS
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

warnings.filterwarnings("ignore")
T = Path.home() / "tmp/mw-1112"
OUT = T / "figs"; OUT.mkdir(exist_ok=True)
CROP = (10, 10, 1620, 1360)
try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 26)
except OSError:
    FONT = ImageFont.load_default(size=26)
NAMES = {"Betelgeuse": (88.79, 7.41), "Rigel": (78.63, -8.20), "Bellatrix": (81.28, 6.35),
         "Saiph": (86.94, -9.67), "Alnitak": (85.19, -1.94), "Alnilam": (84.05, -1.20),
         "Mintaka": (83.00, -0.30), "Orion Nebula": (83.82, -5.39), "Sirius": (101.29, -16.72),
         "Procyon": (114.83, 5.23), "Rosette": (97.98, 4.95), "Cursa": (76.96, -5.09),
         "Arneb": (83.18, -17.82), "Mirzam": (95.67, -17.96), "β Mon": (97.20, -7.03),
         "M50": (105.70, -8.33), "Seagull Nebula": (105.5, -10.4), "Hubble's Variable Nebula": (99.7, 8.7),
         "Cone / Christmas Tree": (100.24, 9.9), "Horsehead": (85.25, -2.46)}


def stretch(im):
    a = np.asarray(im, np.float32)
    lo = np.percentile(a[CROP[1]:CROP[3], CROP[0]:CROP[2]], 5, axis=(0, 1))
    a = np.clip((a - lo) / (255 - lo), 0, 1) ** 0.8
    return Image.fromarray((a * 255).astype(np.uint8))


def bar(im, L, label):
    d = ImageDraw.Draw(im); y0 = im.height - 50
    d.line([30, y0, 30 + L, y0], fill=(224, 224, 224), width=3)
    for x in (30, 30 + L):
        d.line([x, y0 - 9, x, y0 + 9], fill=(224, 224, 224), width=3)
    d.text((30, y0 + 12), label, fill=(224, 224, 224), font=FONT)


for tag, name in (("O", "orion"), ("A", "monoceros")):
    w = WCS(fits.getheader(T / f"solve/st{tag}.wcs"))
    scale = np.mean(np.abs(np.linalg.eigvals(w.pixel_scale_matrix))) * 3600   # arcsec/px
    L5 = int(round(5 * 3600 / scale))
    im = stretch(Image.open(T / f"hq16-{tag}.png").convert("RGB")).crop(CROP).rotate(180)
    # the camera sees the sky upside down (up is ~159 deg E of N): turned 180 so north is ~20 deg off up, east left
    W_, H_ = im.size
    def topix(c):
        x, y = w.world_to_pixel(c)
        return W_ - 1 - (x - CROP[0]), H_ - 1 - (y - CROP[1])
    plain = im.copy(); bar(plain, L5, "5°"); plain.save(OUT / f"hq16-{name}.jpg", quality=90)
    d = ImageDraw.Draw(im)
    for b, col, wd in [(0, (255, 140, 0), 3), (10, (180, 100, 0), 1), (-10, (180, 100, 0), 1)]:
        l = np.linspace(150, 260, 2000)
        g = SkyCoord(l=l * u.deg, b=np.full_like(l, b) * u.deg, frame="galactic").icrs
        x, y = topix(g)
        for j in range(len(x) - 1):
            if all(-50 < v < im.width + 50 for v in (x[j], x[j + 1])) and all(-50 < v < im.height + 50 for v in (y[j], y[j + 1])):
                d.line([x[j], y[j], x[j + 1], y[j + 1]], fill=col, width=wd)
    sc = SkyCoord([v[0] for v in NAMES.values()] * u.deg, [v[1] for v in NAMES.values()] * u.deg)
    x, y = topix(sc)
    for nm, xi, yi in zip(NAMES, x, y):
        if 15 <= xi < im.width - 15 and 15 <= yi < im.height - 80:
            d.ellipse([xi - 14, yi - 14, xi + 14, yi + 14], outline=(0, 160, 255), width=2)
            d.text((xi + 18, yi - 14), nm, fill=(140, 210, 255), font=FONT)
            print(f"  {name}: {nm} at {xi:.0f},{yi:.0f}")
    bar(im, L5, "5°"); im.save(OUT / f"hq16-{name}-labelled.jpg", quality=90)
    print(name, f"{scale:.1f} arcsec/px, 5 deg = {L5} px, field {im.width*scale/3600:.1f} x {im.height*scale/3600:.1f} deg")
