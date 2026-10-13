"""Limiting magnitude of the drizzled whole-night stacks, 10-07 (60 s) vs 10-09 (15 s),
and of one frame from each night. Same method as muppet ~/tmp/skyglow/limmag.py
(5 sigma peaks after Gaussian smoothing, matched to Gaia DR3, chance-corrected
50% completeness), same five sky patches, scaled to the 2x drizzle grid.
Run on muppet from ~/tmp/skyglow (Gaia cones cached there) with system python3."""
import glob, json, os, sys, warnings, numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro"))
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
import astropy.units as u
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.spatial import cKDTree
from astro.skyglow import CameraModel, GlowModel, _enu
A = "/mnt/bigstore/astro-data/astrocam-frames/"
loc = EarthLocation(lat=51.3948*u.deg, lon=-0.2923*u.deg)
NIGHTS = {
  "10-07 (60 s)": dict(dir=A + "2026-10-07", stack=A + "2026-10-07/derot-sky-aligned-driz2.fits", ref="2026-10-07T23:05:39"),
  "10-09 (15 s)": dict(dir=A + "2026-10-09", stack=os.path.expanduser("~/tmp/derot1009/derot-sky.fits"), ref="2026-10-09T22:57:47"),
}
# patch centres fixed ON THE SKY, from the 10-07 binned pixels used in limmag.py
cm07 = CameraModel(A + "2026-10-07/skyglow-cammodel.json")
P07 = {"near pole": (710, 520), "field centre": (1150, 650), "Milky Way (Cas)": (1500, 420),
       "Milky Way (Per)": (1750, 850), "below pole": (900, 1000)}
def sky_of_pixel(cm, x, y, T):
    v = cm.unproject(np.array([x]), np.array([y]))[0]
    alt = np.degrees(np.arcsin(v[2])); az = np.degrees(np.arctan2(v[0], v[1])) % 360
    c = SkyCoord(AltAz(az=az*u.deg, alt=alt*u.deg, obstime=T, location=loc, pressure=0)).icrs
    return c.ra.deg, c.dec.deg
SKY = {k: sky_of_pixel(cm07, x, y, Time(NIGHTS["10-07 (60 s)"]["ref"])) for k, (x, y) in P07.items()}

def xy(cm, ra, dec, T):
    aa = SkyCoord(np.atleast_1d(ra)*u.deg, np.atleast_1d(dec)*u.deg).transform_to(AltAz(obstime=T, location=loc, pressure=0))
    return cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))

def detect(img, region, s):
    y0, y1, x0, x1 = region
    sm = gaussian_filter(np.nan_to_num(img[y0:y1, x0:x1]), s)
    sig = 1.4826 * np.median(np.abs(sm - np.median(sm)))
    pk = (sm == maximum_filter(sm, size=int(4 * s + 1))) & (sm > np.median(sm) + 5 * sig)
    yy, xx = np.nonzero(pk)
    return np.stack([xx + x0, yy + y0], 1).astype(float)

bins = np.arange(6, 16.01, 0.5)
def lim50(det, gx, gy, G, region, rmatch, shift):
    y0, y1, x0, x1 = region
    inside = (gx > x0 + 3) & (gx < x1 - 3) & (gy > y0 + 3) & (gy < y1 - 3)
    tr = cKDTree(det)
    hit = tr.query(np.stack([gx[inside], gy[inside]], 1))[0] < rmatch
    rnd = tr.query(np.stack([gx[inside] + shift, gy[inside]], 1))[0] < rmatch
    Gi = G[inside]; comp = []
    for lo in bins[:-1]:
        m = (Gi >= lo) & (Gi < lo + 0.5)
        comp.append(None if m.sum() < 5 else max(0.0, (hit[m].mean() - rnd[m].mean()) / max(1e-9, 1 - rnd[m].mean())))
    for i in range(1, len(comp)):
        a, b = comp[i-1], comp[i]
        if a is not None and b is not None and a >= 0.5 > b:
            return bins[i-1] + 0.25 + 0.5 * (a - 0.5) / (a - b), len(det)
    return None, len(det)

def load_single(night_dir, T):
    files = sorted(glob.glob(night_dir + "/[0-2][0-9]/*.fits.fz"))
    ms = np.array([int(os.path.basename(f).split(".")[0]) for f in files])
    f = files[int(np.argmin(abs(ms - T.unix * 1000)))]
    hd = fits.open(f)[1]; d = hd.data; H, W = d.shape
    g = d[:H//2*2, :W//2*2].reshape(H//2, 2, W//2, 2).sum(axis=(1, 3), dtype=np.float32)
    exp = float(hd.header.get("EXPTIME", 0) or 0)
    t0 = Time(int(os.path.basename(f).split(".")[0]) / 1000, format="unix")
    return GlowModel(night_dir + "/skyglow-model.npz").subtract(g), t0, f, exp

out = {}
for night, nd in NIGHTS.items():
    cm = CameraModel(nd["dir"] + "/skyglow-cammodel.json")
    T = Time(nd["ref"])
    S = fits.getdata(nd["stack"]).astype(np.float32)
    single, t0, fpath, exp = load_single(nd["dir"], T)
    print(f"\n{night}: stack {S.shape[1]}x{S.shape[0]}, single {os.path.basename(fpath)} exp {exp}")
    for name, (ra0, dec0) in SKY.items():
        ra, dec, G = np.load(f"gaia_{name.replace(' ', '_').replace('(', '').replace(')', '')}.npy").T
        px, py = (float(v[0]) for v in xy(cm, ra0, dec0, T))
        gx, gy = xy(cm, ra, dec, T)
        # drizzle grid: binned x -> 2x + 0.5
        X, Y = 2 * px + 0.5, 2 * py + 0.5
        reg2 = (int(Y) - 120, int(Y) + 120, int(X) - 120, int(X) + 120)
        if min(reg2) < 0 or reg2[1] > S.shape[0] or reg2[3] > S.shape[1]:
            print(f"  {name:18s} off the stack"); continue
        ls, ns = lim50(detect(S, reg2, 2.0), 2 * gx + 0.5, 2 * gy + 0.5, G, reg2, 3.0, 40)
        # single frame on the binned grid at its own mid-exposure time
        Tm = t0 + (exp / 2 if exp else 30) * u.s
        sx, sy = xy(cm, ra, dec, Tm); cx, cy = (float(v[0]) for v in xy(cm, ra0, dec0, Tm))
        reg1 = (int(cy) - 60, int(cy) + 60, int(cx) - 60, int(cx) + 60)
        l1, n1 = lim50(detect(single, reg1, 1.0), sx, sy, G, reg1, 1.5, 20) if min(reg1) >= 0 and reg1[1] <= single.shape[0] and reg1[3] <= single.shape[1] else (None, 0)
        f = lambda v: "n/a" if v is None else f"{v:.2f}"
        print(f"  {name:18s} single G50 {f(l1)} ({n1} det)   drizzled stack G50 {f(ls)} ({ns} det)")
        out.setdefault(night, {})[name] = {"single": l1, "stack": ls}
json.dump(out, open("limmag2.json", "w"), indent=1)
