"""Do astrocam (north) and eclipticam-v3w (south) share sky on 2026-10-07?
Fixed cameras: compare footprints in alt/az (instant) and in Dec (whole night)."""
import json, numpy as np, sys
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
B = "/mnt/bigstore/astro-data"
ast = CameraModel(f"{B}/astrocam-frames/2026-10-07/skyglow-cammodel-night.json")
ecl = CameraModel("/home/peter/astro/eclipticam-v3w/cammodel-2026-10-07.json")
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
