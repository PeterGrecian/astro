"""Mark the galactic plane, Orion & bright stars on a v3w deep-sweep frame, and
the HQ16 field outline (epoch-4 solve) on a v3w frame. Run on muppet."""
import sys, numpy as np, warnings
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from PIL import Image, ImageDraw
warnings.filterwarnings("ignore")
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time
import astropy.units as u
ds = SourceFileLoader("ds", sys.argv[1]).load_module()
cam, jpg, t_iso, out, binned = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
cm = ds.CameraModel(cam); t = datetime.fromisoformat(t_iso)
H, W = map(int, binned.split("x"))
im = Image.open(jpg).convert("RGB"); sx, sy = im.width / W, im.height / H
d = ImageDraw.Draw(im)
loc = EarthLocation(lat=ds.LAT * u.deg, lon=ds.LON * u.deg)
def pix(sc):
    aa = sc.transform_to(AltAz(obstime=Time(t), location=loc, pressure=0))
    v = ds._enu(np.radians(aa.az.deg), np.radians(aa.alt.deg))
    x, y = cm.project(v); front = v @ cm.b > 0.2
    return x * sx, y * sy, front & (aa.alt.deg > 0)
def line(sc, col, w=2):
    x, y, ok = pix(sc)
    for i in range(len(x) - 1):
        if ok[i] and ok[i + 1] and abs(x[i] - x[i+1]) < 200:
            d.line([x[i], y[i], x[i + 1], y[i + 1]], fill=col, width=w)
mode = sys.argv[7]
if mode == "galaxy":
    l = np.linspace(0, 360, 1441)
    for b, col, w in [(0, (255, 140, 0), 3), (10, (180, 100, 0), 1), (-10, (180, 100, 0), 1)]:
        line(SkyCoord(l=l * u.deg, b=np.full_like(l, b) * u.deg, frame="galactic"), col, w)
    stars = {"Betelgeuse": (88.79, 7.41), "Rigel": (78.63, -8.20), "Bellatrix": (81.28, 6.35), "Saiph": (86.94, -9.67),
             "Alnitak": (85.19, -1.94), "Alnilam": (84.05, -1.20), "Mintaka": (83.00, -0.30), "Sirius": (101.29, -16.72),
             "Procyon": (114.83, 5.23), "Aldebaran": (68.98, 16.51), "Pollux": (116.33, 28.03), "Castor": (113.65, 31.89),
             "Pleiades": (56.75, 24.12), "M42": (83.82, -5.39)}
    sc = SkyCoord([v[0] for v in stars.values()] * u.deg, [v[1] for v in stars.values()] * u.deg)
    x, y, ok = pix(sc)
    for (name, _), xi, yi, k in zip(stars.items(), x, y, ok):
        if k and 0 <= xi < im.width and 0 <= yi < im.height:
            d.ellipse([xi - 9, yi - 9, xi + 9, yi + 9], outline=(0, 160, 255), width=2); d.text((xi + 11, yi - 6), name, fill=(120, 200, 255))
    title = f"v3w deep sweep {t:%Y-%m-%d %H:%M} UTC. Orange: galactic plane (b=0, thick) and b=+-10 deg (thin)"
else:   # HQ16 outline: epoch-4 solve RA 326.03 Dec -16.01 at 2026-11-03 20:27 UTC, 22.41x16.91 deg, up -153.9 E of N
    c = SkyCoord(326.03 * u.deg, -16.01 * u.deg)
    aa0 = c.transform_to(AltAz(obstime=Time("2026-11-03T20:27:00"), location=loc, pressure=0))
    hw, hh, pa = 22.41 / 2, 16.91 / 2, np.radians(-153.9)
    s = np.linspace(-1, 1, 60)
    edge = np.concatenate([np.c_[s * hw, np.full(60, hh)], np.c_[np.full(60, hw), -s * hh],
                           np.c_[-s * hw, np.full(60, -hh)], np.c_[np.full(60, -hw), s * hh]])
    # tangent-plane (xi east, eta north) at the solve, image x right, y up rotated by pa
    xi = edge[:, 0] * np.cos(pa) + edge[:, 1] * np.sin(pa)
    eta = -edge[:, 0] * np.sin(pa) + edge[:, 1] * np.cos(pa)
    pts = c.spherical_offsets_by(-xi * u.deg, eta * u.deg)   # -xi: image right = west when up is north
    # fixed in alt-az: carry the solve-time alt-az outline to frame time t
    aa = pts.transform_to(AltAz(obstime=Time("2026-11-03T20:27:00"), location=loc, pressure=0))
    v = ds._enu(np.radians(aa.az.deg), np.radians(aa.alt.deg))
    x, y = cm.project(v); x, y = x * sx, y * sy
    d.line(list(zip(x, y)) + [(x[0], y[0])], fill=(255, 220, 0), width=3)
    v0 = ds._enu(np.radians(aa0.az.deg), np.radians(aa0.alt.deg)); x0, y0 = cm.project(v0)
    d.text((x0 * sx - 20, y0 * sy), "HQ16", fill=(255, 220, 0))
    title = f"v3w {t:%Y-%m-%d %H:%M} UTC. Yellow: HQ16 field (epoch-4 solve 11-03, pointing unchanged since; 22.4 x 16.9 deg)"
d.rectangle([0, 0, im.width, 22], fill=(0, 0, 0)); d.text((8, 5), title, fill=(255, 255, 0))
L = cm.f * np.radians(10) * sx          # 10 deg at the optical centre (fisheye: shrinks a little outwards)
y0 = im.height - 30; d.rectangle([20, y0 - 8, 40 + L, y0 + 22], fill=(0, 0, 0))
d.line([30, y0, 30 + L, y0], fill=(255, 255, 255), width=3); d.text((30, y0 + 6), "10 deg (at centre)", fill=(255, 255, 255))
im.save(out, quality=88); print(out, im.size)
