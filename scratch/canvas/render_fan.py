#!/usr/bin/env python3
"""The whole night as the sky saw it: astrocam 2026-10-07, all clean frames, `derot-sky stack --canvas`
(equidistant sky canvas at REFUTC, not cropped to one frame), so the frame's edges are dragged round
the pole into a fan. Labels from canvas-model.json at REFUTC; the 23:50 frame's outline for scale.
Usage: render_fan.py <stack dir> [<stretch-from stack dir> [<title> [<subtitle>]]]   (writes fan.jpg, fan-labelled.jpg there)
With a second dir, the stretch (ADU -> grey) is taken from that stack, so a series shares one stretch."""
import sys, json, numpy as np, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); sys.path.insert(0, str(Path.home() / "astro"))
from astro.skyglow import CameraModel, _enu
from astropy.io import fits
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
from astropy.time import Time
import astropy.units as u
from PIL import Image, ImageDraw, ImageFont
D = Path(sys.argv[1]); S = fits.getdata(D / "derot-sky.fits", 0); Wt = fits.getdata(D / "derot-sky.fits", 1)
hdr = fits.getheader(D / "derot-sky.fits"); T = Time(hdr["REFUTC"].replace("+00:00", "")); N = hdr["NFRAMES"]
cv = CameraModel(json.load(open(D / "canvas-model.json")))
cam = CameraModel(Path("/mnt/muppet/bigstore/astrocam-frames/2026-10-07/skyglow-cammodel-night.json".replace("/mnt/muppet/bigstore", "/mnt/bigstore/astro-data")))
fr = AltAz(obstime=T, location=EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg), pressure=0)
PXDEG = cv.f * np.pi / 180
# Wt is normalised to its peak (the pole, in every frame), so a fixed fraction
# would black out edges that only a few frames reached, more so the deeper the
# stack. Cut on absolute coverage instead: about 1.5 frames' worth.
good = (Wt > min(0.05, 1.5 / max(N, 1))) & np.isfinite(S)
# stretch on the deep part (>= 25% coverage) so the thin edges are not what sets it
Sref, Wref = (fits.getdata(Path(sys.argv[2]) / "derot-sky.fits", 0), fits.getdata(Path(sys.argv[2]) / "derot-sky.fits", 1)) if len(sys.argv) > 2 else (S, Wt)
deep = (Wref > 0.25) & np.isfinite(Sref); v = Sref[deep]
sig = 1.4826 * np.median(np.abs(v - np.median(v))); lo, hi = np.median(v) - 1.5 * sig, np.percentile(v, 99.7)
g = np.clip((np.nan_to_num(S, nan=lo) - lo) / (hi - lo), 0, None); g = np.arcsinh(14 * g) / np.arcsinh(14)
g[~good] = 0
img = Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).convert("RGB"); img.save(D / "fan.jpg", quality=92)
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40); Fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
d = ImageDraw.Draw(img, "RGBA"); AMBER, BLUE, GREY = (255, 149, 0), (0, 122, 255), (142, 142, 147)
def pxy(sc):
    a = sc.transform_to(fr); x, y = cv.project(_enu(np.radians(a.az.deg), np.radians(a.alt.deg))); return np.atleast_1d(x), np.atleast_1d(y)
l = np.arange(0, 360, 0.5); x, y = pxy(SkyCoord(l=l * u.deg, b=0 * l * u.deg, frame=Galactic))
ok = (x > 0) & (x < img.width) & (y > 0) & (y < img.height)
for i in range(len(l) - 1):
    if ok[i] and ok[i + 1] and i % 4 < 2: d.line([x[i], y[i], x[i + 1], y[i + 1]], fill=BLUE + (200,), width=4)
j = np.where(ok)[0]
if j.size: d.text((x[j[len(j) // 3]] + 20, y[j[len(j) // 3]]), "galactic plane", fill=BLUE, font=Fs)
for name, ra, dec, dx, dy in [("Polaris", 37.955, 89.264, 24, -10), ("Capella", 79.172, 45.998, 24, -10), ("Mirfak", 51.081, 49.861, 24, -10),
                              ("Double Cluster", 34.75, 57.13, 24, -10), ("Kochab", 222.676, 74.156, 24, -10), ("Deneb", 310.358, 45.280, 24, -10),
                              ("Vega", 279.234, 38.784, 24, -10), ("Dubhe", 165.932, 61.751, 24, -10)]:
    x, y = pxy(SkyCoord(ra=ra * u.deg, dec=dec * u.deg)); x, y = float(x[0]), float(y[0])
    if 0 < x < img.width and 0 < y < img.height and good[int(y), int(x)]:
        d.ellipse([x - 18, y - 18, x + 18, y + 18], outline=AMBER, width=3); d.text((x + dx, y + dy), name, fill=AMBER, font=Fs)
cas = [(2.295, 59.150), (10.127, 56.537), (14.177, 60.717), (21.454, 60.235), (28.599, 63.670)]
x, y = pxy(SkyCoord(ra=[c[0] for c in cas] * u.deg, dec=[c[1] for c in cas] * u.deg)); d.line(list(zip(x, y)), fill=AMBER + (160,), width=2)
d.text((x[2] - 60, y[2] - 70), "Cassiopeia", fill=AMBER, font=Fs)
# one frame's outline at REFUTC (camera border -> sky -> canvas)
t = np.arange(0, 2304, 8.0); s_ = np.arange(0, 1296, 8.0)
bx = np.r_[t, np.full(s_.size, 2303.0), t[::-1], np.zeros(s_.size)]; by = np.r_[np.zeros(t.size), s_, np.full(t.size, 1295.0), s_[::-1]]
x, y = cv.project(cam.unproject(bx, by)); d.line(list(zip(x, y)) + [(x[0], y[0])], fill=GREY + (220,), width=3)
d.text((x[0] + 10, y[0] + 10), "one frame (23:50 UTC)", fill=GREY, font=Fs)
L = 10 * PXDEG; d.line([40, img.height - 60, 40 + L, img.height - 60], fill=(255, 255, 255), width=6); d.text((40, img.height - 110), "10 deg", fill=(255, 255, 255), font=Fs)
fj = json.load(open(D / "derot-sky-frames.json")); t0, t1 = fj[0][0][11:16], fj[-1][0][11:16]
if len(sys.argv) > 3:
    d.text((40, 30), sys.argv[3].format(N=N, t0=t0, t1=t1), fill=(224, 224, 224), font=F)
    d.text((40, 80), (sys.argv[4] if len(sys.argv) > 4 else "same sky canvas and the same stretch as the whole-night image").format(N=N, t0=t0, t1=t1), fill=GREY, font=Fs)
else:
    d.text((40, 30), f"astrocam, the whole night of 7-8 Oct 2026: {N} frames of 60 s, {t0}-{t1} UTC", fill=(224, 224, 224), font=F)
    d.text((40, 80), "looking north from Surbiton; the sky turned 135 deg about Polaris and the frame's edges with it", fill=GREY, font=Fs)
img.save(D / "fan-labelled.jpg", quality=92); print("wrote", D / "fan.jpg", D / "fan-labelled.jpg", img.size)
