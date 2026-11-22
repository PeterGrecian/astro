"""Do astrocam (north) and eclipticam-v3w (south) share sky on 2026-10-07?
Fixed cameras: compare footprints in alt/az (instant) and in Dec (whole night)."""
import json, numpy as np, sys
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
B = "/mnt/bigstore/astro-data"
ast = CameraModel(sys.argv[1] if len(sys.argv) > 1 else f"{B}/astrocam-frames/2026-10-07/skyglow-cammodel-night.json")
ecl = CameraModel(sys.argv[2] if len(sys.argv) > 2 else "/home/peter/astro/eclipticam-v3w/cammodel-2026-10-07.json")
LAT = np.radians(51.3948)
def foot(cm, W, H, n=60):
    x, y = np.meshgrid(np.linspace(0, W - 1, n), np.linspace(0, H - 1, n))
    V = cm.unproject(x.ravel(), y.ravel()).reshape(-1, 3)
    ok = np.isfinite(V).all(1) & (V[:, 2] > 0)      # above horizon
    return V[ok] / np.linalg.norm(V[ok], axis=1)[:, None]
def altaz(V):
    return np.degrees(np.arcsin(V[:, 2])), np.degrees(np.arctan2(V[:, 0], V[:, 1])) % 360
def dec(V):  # ENU -> declination
    return np.degrees(np.arcsin(np.sin(LAT) * V[:, 2] + np.cos(LAT) * V[:, 1]))
for name, cm in (("astrocam", ast), ("eclipticam", ecl)):
    print(name, {k: cm.p.get(k) for k in ("W", "H", "width", "height", "shape", "cx", "cy", "f")})
A = foot(ast, *[int(v) for v in (ast.p.get("W", 2 * ast.p["cx"]), ast.p.get("H", 2 * ast.p["cy"]))])
E = foot(ecl, 2304, 1296)
for name, V in (("astrocam", A), ("eclipticam", E)):
    al, az = altaz(V); d = dec(V)
    print(f"{name}: alt {al.min():.0f}..{al.max():.0f}  az {np.percentile(az,1):.0f}..{np.percentile(az,99):.0f}  dec {d.min():.0f}..{d.max():.0f}  n={len(V)}")
sep = np.degrees(np.arccos(np.clip(E @ A.T, -1, 1))).min(1)
print(f"instant: closest eclipticam ray to astrocam footprint {sep.min():.1f} deg; "
      f"fraction of eclipticam within 1 deg of astrocam {np.mean(sep < 1):.3f}")
da, de = dec(A), dec(E)
print(f"whole night: dec overlap {max(da.min(), de.min()):.0f}..{min(da.max(), de.max()):.0f}")

# whole-night sky overlap: footprints in (HA, Dec) swept over the dark window -> RA/Dec cells
if len(sys.argv) > 3:
    from astropy.time import Time
    from astropy.coordinates import EarthLocation
    import astropy.units as u
    loc = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
    t = Time(sys.argv[3]) + np.arange(0, float(sys.argv[4]) * 60 + 1, 5) * u.min
    lst = t.sidereal_time("apparent", longitude=loc.lon).deg
    def cells(cm, W, H):
        V = foot(cm, W, H, 120); d = dec(V)
        ha = np.degrees(np.arctan2(-V[:, 0], np.cos(LAT) * V[:, 2] - np.sin(LAT) * V[:, 1]))  # HA west +
        ra = (lst[:, None] - ha[None, :]) % 360
        return {(int(r), int(dd + 90)) for r, dd in zip(ra.ravel(), np.repeat(d[None, :], len(lst), 0).ravel())}
    cA = cells(ast, 2304, 1296); cE = cells(ecl, 2304, 1296); both = cA & cE
    print(f"night {sys.argv[3]} +{sys.argv[4]} h: 1-deg cells astrocam {len(cA)}, eclipticam {len(cE)}, shared {len(both)}")
    if both:
        r = np.array(sorted(both)); print("  shared RA", r[:, 0].min(), "..", r[:, 0].max(), " Dec", r[:, 1].min() - 90, "..", r[:, 1].max() - 90)
