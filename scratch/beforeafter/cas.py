"""Cassiopeia close-up for /astro/project (mywebsite, Peter 2026-11-24): a whole-night stack oriented to its
reference time (first frame), 2x, the strip's stretch recipe, W stars labelled, 2 deg bar.
Usage: cas.py <stack dir> <cammodel json> <out jpg> <label>"""
import sys, numpy as np, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel, _enu
from astropy.io import fits
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time; import astropy.units as u
from PIL import Image, ImageDraw, ImageFont
D, CM, OUT, LAB = sys.argv[1:5]
S = fits.getdata(f"{D}/derot-sky.fits", 0).astype(np.float32); Wt = fits.getdata(f"{D}/derot-sky.fits", 1)
T = Time(fits.getheader(f"{D}/derot-sky.fits")["REFUTC"].replace("+00:00", "")); cm = CameraModel(CM)
fr = AltAz(obstime=T, location=EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg), pressure=0)
W = [("Caph", 2.295, 59.150), ("Schedar", 10.127, 56.537), ("Gamma Cas", 14.177, 60.717), ("Ruchbah", 21.454, 60.235), ("Segin", 28.599, 63.670)]
a = SkyCoord([w[1] for w in W] * u.deg, [w[2] for w in W] * u.deg).transform_to(fr)
x, y = cm.project(_enu(np.radians(a.az.deg), np.radians(a.alt.deg))); x, y = np.asarray(x), np.asarray(y)
print("W stars px:", np.round(x), np.round(y))
good = (Wt > 0.3 * Wt.max()) & np.isfinite(S)
LO, HI = np.percentile(S[good], 5), np.percentile(S[good], 99.8); GAIN = 12.0
g = np.clip((np.nan_to_num(S, nan=LO) - LO) / (HI - LO), 0, None); g = (np.clip(np.arcsinh(GAIN * g) / np.arcsinh(GAIN), 0, 1) * 255).astype(np.uint8)
g[Wt < 0.05 * Wt.max()] = 0
cx, cy = x.mean(), y.mean(); hw = max(np.ptp(x), np.ptp(y)) / 2 + 70
bw, bh = int(2 * hw), int(2 * hw * 0.75)
x0, y0 = int(max(0, min(S.shape[1] - bw, cx - bw / 2))), int(max(0, min(S.shape[0] - bh, cy - bh / 2)))
Z = 1200 / bw
img = Image.fromarray(g[y0:y0 + bh, x0:x0 + bw]).resize((1200, round(bh * Z)), Image.LANCZOS).convert("RGB")
d = ImageDraw.Draw(img, "RGBA"); F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
AM = (255, 149, 0)
for (n, *_), xi, yi in zip(W, x, y):
    X, Y = (xi - x0) * Z, (yi - y0) * Z; d.ellipse([X - 22, Y - 22, X + 22, Y + 22], outline=AM + (200,), width=2); d.text((X + 28, Y - 14), n, fill=AM, font=F)
d.text((16, 12), LAB, fill=(224, 224, 224), font=F)
L = 2 * cm.f * np.pi / 180 * Z; H = img.height
d.line([16, H - 28, 16 + L, H - 28], fill=(255, 255, 255), width=4); d.text((16, H - 62), "2 deg", fill=(255, 255, 255), font=F)
img.save(OUT, quality=92); print("wrote", OUT, img.size, f"box {bw}x{bh} binned px at x{Z:.2f}")
