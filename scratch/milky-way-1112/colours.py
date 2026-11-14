#!/usr/bin/env python3
"""Star colours in raw v3w frames (night 2026-11-12, 03:00-04:50 UTC): R/G and
B/G of aperture flux (17x17 binned box, ring background) per Bayer channel,
on derot-sky's 2x2-sum scale, every 6th frame. Run on muppet from ~/astro."""
import glob, os, warnings
import numpy as np
from importlib.machinery import SourceFileLoader
from datetime import datetime, timezone, timedelta
warnings.filterwarnings("ignore")
os.environ.setdefault("DEROT_CAMERA", "eclipticam-v3w")
an = SourceFileLoader("an", os.path.expanduser("~/astro/bin/derot-annotate")).load_module(); ds = an.ds
from astropy.coordinates import SkyCoord
import astropy.units as u
nd = an.night_dir("2026-11-12"); cm = ds.CameraModel(str(nd / "skyglow-cammodel.json"))
S = {"Betelgeuse": (88.79, 7.41, 1.85), "Aldebaran": (68.98, 16.51, 1.54), "Procyon": (114.83, 5.23, 0.42),
     "Sirius": (101.29, -16.72, 0.00), "Rigel": (78.63, -8.20, -0.03), "Bellatrix": (81.28, 6.35, -0.22),
     "Saiph": (86.94, -9.67, -0.18)}
sc = SkyCoord([v[0] for v in S.values()] * u.deg, [v[1] for v in S.values()] * u.deg)
t0, t1 = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc), datetime(2026, 11, 13, 4, 50, tzinfo=timezone.utc)
res = {k: [] for k in S}
for f in sorted(glob.glob(str(nd / "v3w/0[34]/*.fits.fz")))[::6]:
    t = datetime.fromtimestamp(int(os.path.basename(f)[:13]) / 1000, timezone.utc) + timedelta(seconds=30)
    if not t0 <= t <= t1:
        continue
    x, y, ok = an.project(cm, sc, t)
    ch = {c: ds.load_binned(f, c) for c in ("R", "G", "B")}
    for k, xi, yi, o in zip(S, x, y, ok):
        if not o or not (20 < xi < 2284 and 20 < yi < 1276):
            continue
        xi, yi = int(round(xi)), int(round(yi))
        fl = {}
        for c, a in ch.items():
            box = a[yi - 8:yi + 9, xi - 8:xi + 9]
            ring = np.concatenate([a[yi - 14:yi + 15, xi - 14:xi - 10].ravel(), a[yi - 14:yi + 15, xi + 11:xi + 15].ravel()])
            fl[c] = box.sum() - np.median(ring) * box.size
            fl[c + "pk"] = box.max()
        res[k].append(fl)
print("star         B-V    n   R/G   B/G  peak R/G/B (2x2-sum; saturation ~3836)")
for k, L in res.items():
    if not L:
        print(f"{k:11s} not in frame"); continue
    m = lambda key: np.median([l[key] for l in L])
    r = np.median([l["R"] / l["G"] for l in L]); b = np.median([l["B"] / l["G"] for l in L])
    print(f"{k:11s} {S[k][2]:5.2f}  {len(L):3d}  {r:5.2f} {b:5.2f}  {m('Rpk'):5.0f} {m('Gpk'):5.0f} {m('Bpk'):5.0f}")
