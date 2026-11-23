"""Star list for the HQ16 nightly derot model: pick the Hipparcos V cut by detection rate on the fit frame,
then list every star in the declination band HQ16 sweeps through a night (field is fixed alt-az).
Usage: hq16stars.py <model json in> <model json out>"""
import json, os, sys, numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
from scipy.spatial import cKDTree
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
m = json.load(open(sys.argv[1])); cam = CameraModel(m); W, H = 2028, 1520
t = Time(m["fit_utc"])
ax = fits.getdata(os.path.expanduser("~/tmp/allcam/solve/hq16.axy")); tree = cKDTree(np.c_[ax["X"] - 1, ax["Y"] - 1])
hip = np.load("/home/peter/astro/scratch/saturn-walk/hip75-allsky.npy"); print("hip cols", hip.shape)
sc = SkyCoord(hip[:, 0] * u.deg, hip[:, 1] * u.deg); aa = sc.transform_to(AltAz(obstime=t, location=LOC, pressure=0))
V = np.c_[np.cos(aa.alt.rad) * np.sin(aa.az.rad), np.cos(aa.alt.rad) * np.cos(aa.az.rad), np.sin(aa.alt.rad)]
x, y = cam.project(V); inn = (x > 10) & (x < W - 10) & (y > 10) & (y < H - 10) & ((V @ cam.b) > 0) & (aa.alt.deg > 5)
d, _ = tree.query(np.c_[x[inn], y[inn]], distance_upper_bound=3); det = np.isfinite(d); mag = hip[inn, 2]
for lo in np.arange(3, 7.5, 0.5):
    s = (mag >= lo) & (mag < lo + 0.5); print(f"V {lo:.1f}-{lo + .5:.1f}: {s.sum():3d} in frame, {det[s].mean() * 100 if s.any() else 0:4.0f}% detected")
cut = float(sys.argv[3]) if len(sys.argv) > 3 else None
# declination band the fixed field sweeps: corners' dec at the fit time (dec is invariant for a fixed alt-az camera)
ex = np.r_[np.linspace(0, W - 1, 50), np.full(50, W - 1.0), np.linspace(W - 1, 0, 50), np.zeros(50)]
ey = np.r_[np.zeros(50), np.linspace(0, H - 1, 50), np.full(50, H - 1.0), np.linspace(H - 1, 0, 50)]
Ve = cam.unproject(ex, ey).reshape(-1, 3); alt = np.arcsin(np.clip(Ve[:, 2], -1, 1)); az = np.arctan2(Ve[:, 0], Ve[:, 1])
ed = SkyCoord(AltAz(alt=alt * u.rad, az=az * u.rad, obstime=t, location=LOC, pressure=0)).icrs.dec.deg
lo, hi = ed.min() - 1, ed.max() + 1; print(f"dec band {lo:.1f} .. {hi:.1f}")
if cut:
    sel = (hip[:, 1] > lo) & (hip[:, 1] < hi) & (hip[:, 2] < cut)
    m["stars_radec_j2000"] = [[round(float(a), 8), round(float(b), 8)] for a, b in hip[sel, :2]]
    m["stars_note"] = (f"Hipparcos V<{cut} (VizieR I/239, hip75-allsky.npy), {sel.sum()} stars, in the declination band "
                       f"{lo:.1f}..{hi:.1f} that HQ16's fixed field sweeps through a night (all RA). Cut chosen by detection "
                       f"within 3 px on the fit frame (60 s sub, 11-13 01:01 UTC): fainter stars are mostly undetected, and "
                       f"derot-sky refine takes the brightest pixel within 3 px of EVERY listed star, so they would add noise. "
                       f"astro-science 2026-11-23, scratch/allcam/hq16stars.py.")
    json.dump(m, open(sys.argv[2], "w"), indent=1); print("wrote", sys.argv[2], sel.sum(), "stars")
