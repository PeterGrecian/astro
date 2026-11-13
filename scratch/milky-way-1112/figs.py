#!/usr/bin/env python3
"""Field-note figures: the winter Milky Way in eclipticam-v3w, night 2026-11-12.

Inputs (made on muppet with bin/derot-sky stack, refined camera model and
alignment from the night's own derot run):
  ~/tmp/mw-1112/stack/derot-sky.fits  32 frames 03:40-04:20 UTC, ref 04:00
  ~/tmp/mw-1112/one/derot-sky.fits     2 frames 03:59-04:01 UTC, ref 04:00
Writes ~/tmp/mw-1112/figs/{deep,labelled,compare}.jpg, privacy-cropped, each
with a 10 deg bar, and prints the band brightness against the sky.

Run on muppet from ~/astro:  .venv/bin/python scratch/milky-way-1112/figs.py
"""
import os
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

import numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw
from scipy.ndimage import median_filter

os.environ.setdefault("DEROT_CAMERA", "eclipticam-v3w")
an = SourceFileLoader("derot_annotate", str(Path.home() / "astro/bin/derot-annotate")).load_module()
ds = an.ds
from astropy.coordinates import SkyCoord, AltAz, EarthLocation   # noqa: E402
from astropy.time import Time                                    # noqa: E402
import astropy.units as u                                        # noqa: E402

T = Path.home() / "tmp/mw-1112"
OUT = T / "figs"; OUT.mkdir(exist_ok=True)
nd = an.night_dir("2026-11-12")
cm = ds.CameraModel(str(nd / "skyglow-cammodel.json"))
t = datetime(2026, 11, 13, 4, 0, tzinfo=timezone.utc)
H = an.privacy_keep(1296)

deep, wd = fits.getdata(T / "stack/derot-sky.fits", 0), fits.getdata(T / "stack/derot-sky.fits", 1)
one = fits.getdata(T / "one/derot-sky.fits", 0)
good = wd > 0.6 * np.nanmax(wd)
v = deep[good & np.isfinite(deep)]
lo, hi = np.percentile(v, 20), np.percentile(v, 99.9)
print(f"stretch lo {lo:.3f} hi {hi:.3f}; well covered {good.mean():.2f}")


def stretch(a, gain=10.0):
    x = np.clip((np.nan_to_num(a, nan=lo) - lo) / (hi - lo), 0, None)
    y = np.arcsinh(gain * x) / np.arcsinh(gain)
    return (np.clip(y, 0, 1) * 255).astype(np.uint8)


CROP = (700, 330, 1820, 1060)   # x0, y0, x1, y1: the region every frame of the 40 min covers (weight > 0.95)
from PIL import ImageFont                                        # noqa: E402
try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 22)
except OSError:
    FONT = ImageFont.load_default(size=22)


def img(a, crop=False):
    g = stretch(a)[:H]
    im = Image.fromarray(np.dstack([g, g, g]))
    return im.crop(CROP) if crop else im


def bar(im, L, label):
    d = ImageDraw.Draw(im)
    y0 = im.height - 30
    y0 = im.height - 40
    d.line([30, y0, 30 + L, y0], fill=(224, 224, 224), width=3)
    for xx in (30, 30 + L):
        d.line([xx, y0 - 8, xx, y0 + 8], fill=(224, 224, 224), width=3)
    d.text((30, y0 + 10), label, fill=(224, 224, 224), font=FONT)


L10 = cm.f * np.radians(10)
im = img(deep, True); bar(im, L10, "10°")
im.save(OUT / "deep.jpg", quality=90)

im = img(deep, True); d = ImageDraw.Draw(im)
for b, col, w in [(0, (255, 140, 0), 3), (10, (180, 100, 0), 1), (-10, (180, 100, 0), 1)]:
    x, y, ok = an.project(cm, an.galactic(b), t)
    for j in range(len(x) - 1):
        if ok[j] and ok[j + 1] and abs(x[j] - x[j + 1]) < 200:
            d.line([x[j] - CROP[0], y[j] - CROP[1], x[j + 1] - CROP[0], y[j + 1] - CROP[1]], fill=col, width=w)
names = dict(an.STARS); names.update({"Adhara": (104.66, -28.97), "Wezen": (107.10, -26.39),
                                      "Alhena": (99.43, 16.40), "Rosette": (97.98, 4.95),
                                      "M41": (101.50, -20.72), "Naos": (120.90, -40.00)})
sc = SkyCoord([q[0] for q in names.values()] * u.deg, [q[1] for q in names.values()] * u.deg)
x, y, ok = an.project(cm, sc, t)
for nm, xi, yi, k in zip(names, x, y, ok):
    xi, yi = xi - CROP[0], yi - CROP[1]
    if k and 0 <= xi < im.width and 0 <= yi < im.height - 60:
        d.ellipse([xi - 12, yi - 12, xi + 12, yi + 12], outline=(0, 160, 255), width=2)
        d.text((xi + 15, yi - 12), nm, fill=(140, 210, 255), font=FONT)
        print(f"  {nm:14s} x {xi:6.0f} y {yi:6.0f}")
bar(im, L10, "10°")
im.save(OUT / "labelled.jpg", quality=90)

# galactic latitude of every output pixel, for the band measurement and the compare crop
yy, xx = np.mgrid[0:1296:4, 0:2304:4]
vv = cm.unproject(xx.ravel().astype(float), yy.ravel().astype(float)) if hasattr(cm, "unproject") else None
if vv is not None:
    az = np.degrees(np.arctan2(vv[:, 0], vv[:, 1])); alt = np.degrees(np.arcsin(np.clip(vv[:, 2], -1, 1)))
    loc = EarthLocation(lat=ds.LAT * u.deg, lon=ds.LON * u.deg)
    g = SkyCoord(AltAz(az=az * u.deg, alt=alt * u.deg, obstime=Time(t), location=loc, pressure=0)).galactic
    B = g.b.deg.reshape(xx.shape); Lg = g.l.deg.reshape(xx.shape)
    sm = median_filter(np.nan_to_num(deep, nan=0), size=9)[::4, ::4]   # stars removed
    gm = good[::4, ::4] & (yy < H)
    band = gm & (np.abs(B) < 5); off = gm & (np.abs(B) > 15) & (np.abs(B) < 30)
    print(f"band |b|<5: n {band.sum()} median {np.median(sm[band]):.3f} ADU; "
          f"off 15<|b|<30: n {off.sum()} median {np.median(sm[off]):.3f}; "
          f"l range in band {Lg[band].min():.0f}..{Lg[band].max():.0f}")
    for l0 in range(190, 260, 10):
        m = band & (Lg >= l0) & (Lg < l0 + 10)
        if m.sum() > 50:
            print(f"   l {l0}-{l0+10}: band {np.median(sm[m]):.3f} n {m.sum()}")
else:
    print("no unproject on CameraModel; band measurement skipped")

# one frame vs the stack, same stretch, a 600x400 crop around the plane near Monoceros
x, y, ok = an.project(cm, SkyCoord([100.0] * u.deg, [0.0] * u.deg), t)
cx, cy = int(np.clip(x[0], 300, 2304 - 300)), int(np.clip(y[0], 200, H - 200))
c1 = img(one).crop((cx - 300, cy - 200, cx + 300, cy + 200))
c2 = img(deep).crop((cx - 300, cy - 200, cx + 300, cy + 200))
cmp_ = Image.new("RGB", (1210, 400), (22, 22, 22)); cmp_.paste(c1, (0, 0)); cmp_.paste(c2, (610, 0))
d = ImageDraw.Draw(cmp_)
d.text((12, 8), "2 minutes", fill=(224, 224, 224), font=FONT); d.text((622, 8), "40 minutes, stars held still", fill=(224, 224, 224), font=FONT)
bar(cmp_, cm.f * np.radians(5), "5°")
cmp_.save(OUT / "compare.jpg", quality=90)
print("crop centre", cx, cy, "->", OUT)
