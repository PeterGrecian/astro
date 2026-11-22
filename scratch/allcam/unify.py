#!/usr/bin/env python3
"""The grand unified sky: all four cameras' whole-night canvases of 2026-11-12/13 on ONE fisheye.
Equidistant, centred on the zenith at REF (23:45 UTC), out to 120 deg from it (sky that set or rose
during the night lies beyond the REF horizon, drawn as a circle). Each canvas is re-projected through
its canvas-model.json and the sidereal rotation between its REFUTC and REF. Own stretch per camera
(median - 1.5 sigma .. 99.7 pct of the well-covered part, asinh); layered v3w, astrocam, hq16, hqfs;
coloured outline per camera. Insets: hqfs (a 2.3 deg disc round the pole) and hq16, at their own scale.
Usage: unify.py <name>=<stack dir> ... ; writes ~/tmp/allcam/unified{,-labelled}.jpg"""
import json, sys, os, numpy as np, cv2, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel, _enu, SIDEREAL_RAD_PER_S
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
import astropy.units as u
from PIL import Image, ImageDraw, ImageFont
REF = Time("2026-11-12T23:45:00"); LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
OUT = Path.home() / "tmp/allcam"; NPX = 4800; RMAX = np.radians(120)
F = (NPX / 2 - 40) / RMAX
uv = CameraModel(dict(lat=51.3948, lon=-0.2923, mirror=-1, az0=0.0, alt0=np.pi / 2, roll=0.0, f=F, k=0.0, cx=NPX / 2, cy=NPX / 2))
# zenith axis: CameraModel takes e1 = east there; roll so that north is up (south at the bottom), east left (sky view)
def rot(axis, ang):
    a = axis / np.linalg.norm(axis); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
COL = {"v3w": (255, 149, 0), "astrocam": (0, 122, 255), "hq16": (255, 59, 48), "hqfs": (52, 199, 89)}
ORDER = ["v3w", "astrocam", "hq16", "hqfs"]
srcs = dict(a.split("=", 1) for a in sys.argv[1:])
gy, gx = np.mgrid[0:NPX, 0:NPX].astype(np.float32)
Vu = uv.unproject(gx, gy).reshape(-1, 3)
inside = (np.hypot(gx - NPX / 2, gy - NPX / 2) <= RMAX * F).ravel()
rgb = np.zeros((NPX, NPX, 3), np.float32); covered = {}
MINW = {"v3w": 0.1}   # v3w's frame corner reaches the bottom-right edge only briefly (~4% weight), where the
                      # glow fit fails and a bright smear survives; drop that thin edge
def grey(S, Wt, N, minw=0.0):
    good = (Wt > max(minw, min(0.05, 1.5 / max(N, 1)))) & np.isfinite(S); deep = (Wt > 0.25) & np.isfinite(S); v = S[deep]
    sig = 1.4826 * np.median(np.abs(v - np.median(v))); lo, hi = np.median(v) - 1.5 * sig, np.percentile(v, 99.7)
    g = np.clip((np.nan_to_num(S, nan=lo) - lo) / (hi - lo), 0, None); g = np.arcsinh(14 * g) / np.arcsinh(14); g[~good] = 0
    return np.clip(g, 0, 1).astype(np.float32), good.astype(np.float32)
for name in ORDER:
    if name not in srcs: continue
    D = Path(srcs[name]); S = fits.getdata(D / "derot-sky.fits", 0); Wt = fits.getdata(D / "derot-sky.fits", 1)
    h = fits.getheader(D / "derot-sky.fits"); tc = Time(h["REFUTC"].replace("+00:00", ""))
    cv = CameraModel(json.load(open(D / "canvas-model.json")))
    g, good = grey(S, Wt, h["NFRAMES"], MINW.get(name, 0.0))
    dt = (tc - REF).to_value("s")                       # sky at REF -> where it is at the canvas's REFUTC
    V = Vu @ rot(cv.pole, -SIDEREAL_RAD_PER_S * dt).T
    x, y = cv.project(V); fwd = (V @ cv.b) > 0
    mx = np.where(fwd & inside, x, -1).reshape(NPX, NPX).astype(np.float32); my = np.where(fwd & inside, y, -1).reshape(NPX, NPX).astype(np.float32)
    gg = cv2.remap(g, mx, my, cv2.INTER_AREA if cv.f / F > 2 else cv2.INTER_LINEAR, borderValue=0)
    cc = cv2.remap(good, mx, my, cv2.INTER_LINEAR, borderValue=0) > 0.5
    rgb[cc] = gg[cc, None]                               # later cameras on top
    covered[name] = cc
    print(f"{name}: {h['NFRAMES']} frames, REF {h['REFUTC'][11:16]}, {cc.mean() * 100:.2f}% of the map, native {cv.f * np.pi / 180:.1f} px/deg vs map {F * np.pi / 180:.1f}")
img = Image.fromarray((rgb * 255).astype(np.uint8)); img.save(OUT / "unified.jpg", quality=92)
# ---- labels
d = ImageDraw.Draw(img, "RGBA")
Fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 64); Fm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
for name, cc in covered.items():                         # outline each camera's whole-night footprint
    cs, _ = cv2.findContours(cc.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        if len(c) > 20: d.line([tuple(p[0]) for p in c] + [tuple(c[0][0])], fill=COL[name] + (230,), width=5)
fr = AltAz(obstime=REF, location=LOC, pressure=0)
def pxy(sc):
    a = sc.transform_to(fr); return uv.project(_enu(a.az.rad, a.alt.rad))
th = np.linspace(0, 2 * np.pi, 721)                      # REF horizon and 30/60 deg altitude
for alt, wid in ((0, 4), (30, 2), (60, 2)):
    x, y = uv.project(_enu(th, np.full_like(th, np.radians(alt)))); d.line(list(zip(x, y)), fill=(142, 142, 147, 200), width=wid)
for lab, az in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
    x, y = uv.project(_enu(np.radians(az), np.radians(-3.0))); d.text((float(x) - 20, float(y) - 30), lab, fill=(224, 224, 224), font=Fb)
l = np.linspace(0, 360, 1441); gp = SkyCoord(l=l * u.deg, b=np.zeros_like(l) * u.deg, frame=Galactic)
x, y = pxy(gp); r = np.hypot(np.asarray(x) - NPX / 2, np.asarray(y) - NPX / 2); ok = r < RMAX * F
for i in range(len(l) - 1):
    if ok[i] and ok[i + 1] and i % 6 < 3: d.line([x[i], y[i], x[i + 1], y[i + 1]], fill=(120, 170, 255, 170), width=4)
gc = SkyCoord(l=0 * u.deg, b=0 * u.deg, frame=Galactic); x, y = pxy(gc)
if np.hypot(float(x) - NPX / 2, float(y) - NPX / 2) < RMAX * F:
    d.ellipse([float(x) - 22, float(y) - 22, float(x) + 22, float(y) + 22], outline=(120, 170, 255), width=5)
    d.text((float(x) + 30, float(y) - 20), "galactic centre (below the horizon)", fill=(120, 170, 255), font=Fm)
for name, ra, dec in [("Polaris", 37.955, 89.264), ("Capella", 79.172, 45.998), ("Vega", 279.234, 38.784), ("Deneb", 310.358, 45.28),
                      ("Dubhe", 165.932, 61.751), ("Aldebaran", 68.98, 16.509), ("Betelgeuse", 88.793, 7.407), ("Rigel", 78.634, -8.202),
                      ("Sirius", 101.287, -16.716), ("Pleiades", 56.75, 24.12), ("Fomalhaut", 344.413, -29.622), ("Altair", 297.696, 8.868),
                      ("Castor", 113.65, 31.888), ("Procyon", 114.825, 5.225), ("Double Cluster", 34.75, 57.13)]:
    x, y = pxy(SkyCoord(ra * u.deg, dec * u.deg)); x, y = float(x), float(y)
    if np.hypot(x - NPX / 2, y - NPX / 2) < RMAX * F:
        d.ellipse([x - 16, y - 16, x + 16, y + 16], outline=(255, 214, 10, 220), width=3); d.text((x + 22, y - 22), name, fill=(255, 214, 10), font=Fm)
d.text((60, 40), "Four cameras, one night: 12-13 Nov 2026, Surbiton", fill=(224, 224, 224), font=Fb)
d.text((60, 120), "each camera's whole night on one fisheye of the sky at 23:45 UTC (zenith at centre; grey: horizon, 30, 60 deg)", fill=(142, 142, 147), font=Fm)
yk = 190
for name, lab in (("astrocam", "astrocam (north, wide)"), ("v3w", "eclipticam v3w (south, wide)"), ("hq16", "eclipticam HQ16 (16 mm)"), ("hqfs", "hqfs (FirstScope, 300 mm, at the pole)")):
    if name in covered: d.rectangle([60, yk + 8, 110, yk + 48], outline=COL[name], width=6); d.text((130, yk), lab, fill=COL[name], font=Fm); yk += 64
L = 10 * F * np.pi / 180; d.line([60, NPX - 80, 60 + L, NPX - 80], fill=(255, 255, 255), width=8); d.text((60, NPX - 150), "10 deg (at the centre)", fill=(255, 255, 255), font=Fm)
# insets: native-scale fans
yi = 60
for name, tag in (("hqfs", "hqfs: the pole, whole night"), ("hq16", "HQ16: whole night")):
    if name in srcs and (Path(srcs[name]) / "fan.jpg").exists():
        fan = Image.open(Path(srcs[name]) / "fan.jpg"); s = 1100 / max(fan.size); fan = fan.resize((int(fan.width * s), int(fan.height * s)), Image.LANCZOS)
        X0 = NPX - fan.width - 60; img.paste(fan, (X0, yi)); d.rectangle([X0, yi, X0 + fan.width, yi + fan.height], outline=COL[name], width=6)
        d.text((X0 + 20, yi + 14), tag, fill=COL[name], font=Fm); yi += fan.height + 60
img.save(OUT / "unified-labelled.jpg", quality=90)
img.resize((1600, 1600), Image.LANCZOS).save(OUT / "unified-labelled-web.jpg", quality=85)
print("wrote", OUT / "unified.jpg", OUT / "unified-labelled.jpg")
