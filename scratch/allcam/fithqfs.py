"""hqfs (FirstScope + IMX477, xoverpi) camera model for derot-sky, night 2026-11-12, position 6.
astrometry.net will not solve it (omega PSF, ~45 stars in 1.2 deg), so: Polaris anchors the field;
brute force rotation x mirror x scale of Gaia DR3 (G<13, ~/tmp/allcam/gaia-pole.tsv) about Polaris
against the detected sources; then least-squares CameraModel (k=0) on the matches.
Grid: derot-sky load_binned of the stored 2028x1520 frames -> 1014x760 (x_b = (x_s - 0.5) / 2)."""
import glob, json, os, sys, numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
OUT = os.path.expanduser("~/tmp/allcam")
LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
X = sorted(glob.glob("/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-12/*/20261112T185923Z-*.fits.fz"), key=os.path.basename)
i = 300
t_mid = Time(fits.getheader(X[i], 1)["DATE-OBS"].replace("+00:00", "")) + (5 * 12 + 6) * u.s   # mid of 10 x 12 s
ax = fits.getdata(f"{OUT}/solve/hqfs3.axy")
xs, ys, fl = ax["X"] - 1, ax["Y"] - 1, ax["FLUX"]            # FITS 1-based -> 0-based, stored grid
xb, yb = (xs - 0.5) / 2, (ys - 0.5) / 2
o = np.argsort(-fl); xb, yb, fl = xb[o], yb[o], fl[o]
P0 = np.array([xb[0], yb[0]])                                # Polaris = brightest
print(f"{len(xb)} sources; Polaris at binned {P0.round(1)}")
g = np.array([l.split("\t") for l in open(f"{OUT}/gaia-pole.tsv") if l[:1].strip() and l[0].isdigit()], float)
ra, de, G = g[:, 0], g[:, 1], g[:, 2]
pol = SkyCoord(37.95456067 * u.deg, 89.26410897 * u.deg)
sc = SkyCoord(ra * u.deg, de * u.deg)
off = pol.spherical_offsets_to(sc); xi, eta = off[0].arcsec, off[1].arcsec   # tangent offsets (E, N), arcsec
tree = cKDTree(np.c_[xb[1:60], yb[1:60]])
best = (0,)
for mir in (1, -1):
    for s in np.linspace(3.8, 4.8, 21):                       # arcsec per binned px (theory 4.28)
        for th in np.radians(np.arange(0, 360, 0.5)):
            c, sn = np.cos(th), np.sin(th)
            px = P0[0] + (mir * (c * xi - sn * eta)) / s; py = P0[1] - (sn * xi + c * eta) / s
            k = (G < 12.5) & (px > 0) & (px < 1014) & (py > 0) & (py < 760)
            d, _ = tree.query(np.c_[px[k], py[k]], distance_upper_bound=3)
            n = int(np.isfinite(d).sum())
            if n > best[0]: best = (n, mir, s, th)
print("best similarity: matches %d mirror %d scale %.3f\"/px rot %.1f deg" % (best[0], best[1], best[2], np.degrees(best[3])))
n, mir, s, th = best; c, sn = np.cos(th), np.sin(th)
px = P0[0] + (mir * (c * xi - sn * eta)) / s; py = P0[1] - (sn * xi + c * eta) / s
T2 = cKDTree(np.c_[xb, yb]); d, j = T2.query(np.c_[px, py], distance_upper_bound=4)
m = np.isfinite(d); mx, my, msc = xb[j[m]], yb[j[m]], sc[m]
print(f"{m.sum()} matched pairs for the model fit")
aa = msc.transform_to(AltAz(obstime=t_mid, location=LOC, pressure=0))
alt, az = aa.alt.rad, aa.az.rad
V = np.c_[np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)]
pa = pol.transform_to(AltAz(obstime=t_mid, location=LOC, pressure=0))
base = dict(lat=51.3948, lon=-0.2923, mirror=mir, k=0.0, cx=507.0, cy=380.0)
def model(q):
    return CameraModel(dict(base, az0=q[0], alt0=q[1], roll=q[2], f=q[3]))   # cx, cy fixed at frame centre: with k=0 on a 1 deg field they are degenerate with pointing
def res(q):
    x, y = model(q).project(V); return np.r_[x - mx, y - my]
f0 = 206264.806 / s
# stage 1: free optical centre (fits easily), stage 2: centre fixed at the frame centre, pointing
# taken from stage 1's direction of that pixel, roll scanned finely
def free(q):
    return CameraModel(dict(base, az0=q[0], alt0=q[1], roll=q[2], f=q[3], cx=q[4], cy=q[5]))
def rfree(q):
    x, y = free(q).project(V); return np.r_[x - mx, y - my]
st1 = []
for r0 in np.radians(np.arange(0, 360, 15)):
    r = least_squares(rfree, [pa.az.rad, pa.alt.rad, r0, f0, P0[0], P0[1]], loss="soft_l1", f_scale=1.0)
    st1.append((np.median(np.hypot(*r.fun.reshape(2, -1))), r.x))
m1, q1 = min(st1, key=lambda t: t[0]); print(f"stage 1 (free centre): median {m1:.2f} px")
c = free(q1).unproject(np.array(base["cx"]), np.array(base["cy"])).reshape(3)
az_c, alt_c = np.arctan2(c[0], c[1]), np.arcsin(c[2])
fits_ = []
for r0 in np.radians(np.arange(0, 360, 1.0)):
    q0 = [az_c, alt_c, r0, q1[3]]
    if np.median(np.abs(res(q0))) > 200: continue
    r = least_squares(res, q0, loss="soft_l1", f_scale=1.0); fits_.append((np.median(np.hypot(*r.fun.reshape(2, -1))), r.x))
med, q = min(fits_, key=lambda t: t[0])
e = np.hypot(*res(q).reshape(2, -1))
print(f"model fit: median {med:.2f} px, p90 {np.percentile(e, 90):.2f} px, n {len(e)}; f {q[3]:.0f} px/rad = {206264.806 / q[3]:.3f}\"/px")
out = dict(base, az0=float(q[0]), alt0=float(q[1]), roll=float(q[2]), f=float(q[3]),
           model_note="equidistant (k=0) about the optical axis, fixed alt-az camera; binned 1014x760 grid (load_binned of stored 2028x1520)",
           fit_night="2026-11-12", fit_frames=[X[i], X[i + 9]], fit_utc=t_mid.isot, fit_n=int(len(e)), fit_median_px=float(np.median(e)),
           fit_method="astro-science #1107 scratch/allcam/fithqfs.py: Polaris anchor + brute-force similarity vs Gaia DR3 G<13, then least squares")
json.dump(out, open(f"{OUT}/hqfs-cammodel-2026-11-12.json", "w"), indent=1)
print("alt0 %.3f az0 %.3f deg; pole offset from axis %.3f deg" % (np.degrees(q[1]), np.degrees(q[0]) % 360,
      np.degrees(np.arccos(np.clip(model(q).b @ model(q).pole, -1, 1)))))
