"""eclipticam-hq16 camera model for derot-sky, night 2026-11-12 (epoch 5): CameraModel (equidistant+cubic)
least-squares on astrometry.net's matched stars (.corr of ~/tmp/allcam/solve/hq16, a load_binned-grid frame)."""
import json, os, sys, numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
from scipy.optimize import least_squares
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
OUT = os.path.expanduser("~/tmp/allcam"); LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
FR = "/mnt/bigstore/astro-data/eclipticam-frames/night/2026-11-12/hq16/01/1794531644699.fits.fz"
h = fits.getheader(FR, 1); t = Time(int(os.path.basename(FR).split(".")[0]) / 1000, format="unix") + float(h["EXPTIME"]) / 2 * u.s
c = fits.getdata(f"{OUT}/solve/hq16.corr")
mx, my = c["field_x"] - 1, c["field_y"] - 1
sc = SkyCoord(c["index_ra"] * u.deg, c["index_dec"] * u.deg)
aa = sc.transform_to(AltAz(obstime=t, location=LOC, pressure=0)); alt, az = aa.alt.rad, aa.az.rad
V = np.c_[np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)]
H, W = fits.getdata(f"{OUT}/solve/hq16.fits").shape
print(f"{len(mx)} matched stars on a {W}x{H} grid, t {t.isot}")
w = fits.open(f"{OUT}/solve/hq16.wcs")[0].header
cen = SkyCoord(w["CRVAL1"] * u.deg, w["CRVAL2"] * u.deg).transform_to(AltAz(obstime=t, location=LOC, pressure=0))
best = None
for mir in (1, -1):
    def model(q): return CameraModel(dict(lat=51.3948, lon=-0.2923, mirror=mir, az0=q[0], alt0=q[1], roll=q[2], f=q[3], k=q[4], cx=W / 2, cy=H / 2))
    def res(q): x, y = model(q).project(V); return np.r_[x - mx, y - my]
    for r0 in np.radians(np.arange(0, 360, 10)):
        r = least_squares(res, [cen.az.rad, cen.alt.rad, r0, 206264.806 / 40.2, 0.0], loss="soft_l1")
        m = np.median(np.hypot(*r.fun.reshape(2, -1)))
        if best is None or m < best[0]: best = (m, mir, r.x, r.fun)
m, mir, q, fun = best; e = np.hypot(*fun.reshape(2, -1))
print(f"fit: mirror {mir} median {m:.2f} px p90 {np.percentile(e, 90):.2f}; f {q[3]:.1f} ({206264.806 / q[3]:.2f}\"/px) k {q[4]:.4f}; alt0 {np.degrees(q[1]):.2f} az0 {np.degrees(q[0]) % 360:.2f} roll {np.degrees(q[2]):.2f}")
json.dump(dict(lat=51.3948, lon=-0.2923, mirror=mir, az0=float(q[0]), alt0=float(q[1]), roll=float(q[2]), f=float(q[3]), k=float(q[4]),
               cx=W / 2, cy=H / 2, model_note=f"equidistant+cubic about the optical axis, fixed alt-az camera; binned {W}x{H} grid (load_binned)",
               fit_night="2026-11-12", fit_frame=FR, fit_utc=t.isot, fit_n=int(len(e)), fit_median_px=float(m),
               fit_method="astro-science #1107 scratch/allcam/fithq16.py: astrometry.net .corr matches, least squares"),
          open(f"{OUT}/hq16-cammodel-2026-11-12.json", "w"), indent=1)

# refine: iterate predict -> match detections (hq16.axy) to Hipparcos V<7.5 -> refit
ax = fits.getdata(f"{OUT}/solve/hq16.axy"); dx, dy = ax["X"] - 1, ax["Y"] - 1
from scipy.spatial import cKDTree
hip = np.load("/home/peter/astro/scratch/saturn-walk/hip75-allsky.npy")
hs = SkyCoord(hip[:, 0] * u.deg, hip[:, 1] * u.deg).transform_to(AltAz(obstime=t, location=LOC, pressure=0))
up = hs.alt.deg > 5; ha, hz = hs.alt.rad[up], hs.az.rad[up]
HV = np.c_[np.cos(ha) * np.sin(hz), np.cos(ha) * np.cos(hz), np.sin(ha)]
tree = cKDTree(np.c_[dx, dy])
def model(q): return CameraModel(dict(lat=51.3948, lon=-0.2923, mirror=mir, az0=q[0], alt0=q[1], roll=q[2], f=q[3], k=q[4], cx=q[5], cy=q[6]))
q = np.r_[q, W / 2, H / 2]
for it, tol in enumerate((6, 4, 3, 2.5)):
    x, y = model(q).project(HV); inn = (x > 5) & (x < W - 5) & (y > 5) & (y < H - 5) & ((HV @ model(q).b) > 0)
    d, j = tree.query(np.c_[x[inn], y[inn]], distance_upper_bound=tol); ok = np.isfinite(d)
    Vm, xm, ym = HV[inn][ok], dx[j[ok]], dy[j[ok]]
    r = least_squares(lambda q: np.r_[model(q).project(Vm)[0] - xm, model(q).project(Vm)[1] - ym], q, loss="soft_l1", f_scale=1.0)
    q = r.x; e = np.hypot(*r.fun.reshape(2, -1))
    print(f"iter {it}: {ok.sum()} of {inn.sum()} Hipparcos matched; median {np.median(e):.2f} px p90 {np.percentile(e, 90):.2f}; f {q[3]:.1f} k {q[4]:.4f} c ({q[5]:.0f},{q[6]:.0f})")
mm = json.load(open(f"{OUT}/hq16-cammodel-2026-11-12.json"))
mm.update(az0=float(q[0]), alt0=float(q[1]), roll=float(q[2]), f=float(q[3]), k=float(q[4]), cx=float(q[5]), cy=float(q[6]),
          fit_n=int(len(e)), fit_median_px=float(np.median(e)), fit_method=mm["fit_method"] + "; then iterated against Hipparcos V<7.5 on the frame's detections")
json.dump(mm, open(f"{OUT}/hq16-cammodel-2026-11-12.json", "w"), indent=1)
