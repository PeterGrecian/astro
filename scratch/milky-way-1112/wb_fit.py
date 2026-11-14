#!/usr/bin/env python3
"""White balance for the v3w colour stack from catalogue star colours.

Aperture flux of Hipparcos V<6.5 stars (VizieR I/239, B-V, file
~/tmp/mw-1112/hip-bv.tsv) in the R, G, B derot stacks (night 2026-11-12,
03:40-04:20 UTC, ref 04:00), fit log(R/G) and log(B/G) linear in B-V, and
report the gains that make B-V 0.62 (the Sun) neutral. Run on muppet.
"""
import os, json, warnings
import numpy as np
from importlib.machinery import SourceFileLoader
from pathlib import Path
from datetime import datetime, timezone
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u
warnings.filterwarnings("ignore")
os.environ.setdefault("DEROT_CAMERA", "eclipticam-v3w")
an = SourceFileLoader("an", str(Path.home() / "astro/bin/derot-annotate")).load_module(); ds = an.ds
T = Path.home() / "tmp/mw-1112"
cm = ds.CameraModel(str(an.night_dir("2026-11-12") / "skyglow-cammodel.json"))
rows = [l.split("\t") for l in open(T / "hip-bv.tsv") if l[:1] in " 0123456789" and l.count("\t") == 3]
cat = np.array([[float(v) for v in r] for r in rows if all(v.strip() for v in r)])
t = datetime(2026, 11, 13, 4, 0, tzinfo=timezone.utc)
x, y, ok = an.project(cm, SkyCoord(cat[:, 0] * u.deg, cat[:, 1] * u.deg), t)
st = {c: np.nan_to_num(fits.getdata(T / f"stack-{c}/derot-sky.fits", 0)) for c in "RGB"}
wt = fits.getdata(T / "stack/derot-sky.fits", 1); good = wt > 0.6 * wt.max()
H = an.privacy_keep(1296)
out = []
for (ra, de, V, bv), xi, yi, o in zip(cat, x, y, ok):
    xi, yi = int(round(xi)), int(round(yi))
    if not o or not (30 < xi < 2274 and 30 < yi < H - 30) or not good[yi, xi] or V < 1.5:
        continue
    # the stack sits ~6 px below annotate's projection (refraction/align); take the
    # brightest G pixel within 10 px of the prediction as the star
    w = st["G"][yi - 10:yi + 11, xi - 10:xi + 11]
    j = np.unravel_index(w.argmax(), w.shape); yi, xi = yi + j[0] - 10, xi + j[1] - 10
    f = {}
    for c, a in st.items():
        box = a[yi - 4:yi + 5, xi - 4:xi + 5]
        ann = np.concatenate([a[yi - 12:yi + 13, xi - 12:xi - 7].ravel(), a[yi - 12:yi + 13, xi + 8:xi + 13].ravel()])
        f[c] = box.sum() - np.median(ann) * box.size
    if f["G"] > 0 and f["R"] > 0 and f["B"] > 0:
        out.append((V, bv, f["R"] / f["G"], f["B"] / f["G"], f["G"]))
o = np.array(out)
bright = o[:, 0] < 5.0
print(f"{len(o)} stars measured, {bright.sum()} with V<5")
s = o[bright]
pr = np.polyfit(s[:, 1], np.log(s[:, 2]), 1); pb = np.polyfit(s[:, 1], np.log(s[:, 3]), 1)
rg, bg = np.exp(np.polyval(pr, 0.62)), np.exp(np.polyval(pb, 0.62))
for lo, hi in ((-0.3, 0.2), (0.2, 0.6), (0.6, 1.0), (1.0, 1.4), (1.4, 2.0)):
    m = (s[:, 1] >= lo) & (s[:, 1] < hi)
    if m.any():
        print(f"  B-V {lo:+.1f}..{hi:+.1f}: n {m.sum():3d}  R/G {np.median(s[m,2]):.2f}  B/G {np.median(s[m,3]):.2f}")
print(f"fit at B-V 0.62: R/G {rg:.3f} B/G {bg:.3f} -> gains R x{1/rg:.2f} B x{1/bg:.2f}")
print(f"median B-V of measured stars {np.median(s[:,1]):.2f}")
json.dump({"R": 1 / rg, "G": 1.0, "B": 1 / bg, "n": int(bright.sum())}, open(T / "wb.json", "w"))

# --- check the rendered colour.jpg: per star, jpg (R-B) at the star vs catalogue B-V
from PIL import Image
J = T / "figs/colour.jpg"
if J.exists():
    im = np.asarray(Image.open(J)).astype(int); X0, Y0 = 700, 330
    rows = []
    for (ra, de, V, bv), xi, yi, o in zip(cat, x, y, ok):
        xi, yi = int(round(xi)), int(round(yi))
        if not o or V > 5 or not (30 < xi < 2274 and 30 < yi < H - 30):
            continue
        w = st["G"][yi - 10:yi + 11, xi - 10:xi + 11]; j = np.unravel_index(w.argmax(), w.shape)
        jx, jy = xi + j[1] - 10 - X0, yi + j[0] - 10 - Y0
        if 3 < jx < im.shape[1] - 4 and 3 < jy < im.shape[0] - 4:
            p = im[jy - 3:jy + 4, jx - 3:jx + 4].reshape(-1, 3).mean(0)
            rows.append((bv, p[0] - p[2]))
    r = np.array(rows)
    print(f"jpg check: {len(r)} V<5 stars in the crop")
    for lo, hi in ((-0.3, 0.2), (0.2, 0.6), (0.6, 1.0), (1.0, 1.4), (1.4, 2.0)):
        m = (r[:, 0] >= lo) & (r[:, 0] < hi)
        if m.any():
            print(f"  B-V {lo:+.1f}..{hi:+.1f}: n {m.sum():3d}  jpg R-B {np.median(r[m,1]):+.0f}")
