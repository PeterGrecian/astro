"""hqfs (FirstScope + IMX477) whole-night sky canvas, night 2026-11-12, run 20261112T185923Z (3429 x 12 s).
Fixed alt-az scope pointed 0.34 deg from the pole, so the 1.3 x 1.0 deg field rotates about the pole all
night: the canvas is an equidistant disc centred on the pole at REF, native 4.56"/px.
Background: median of 80 frames spread over the night (stars move, fixed pattern stays), scaled to each
frame's sky level (vignetting is multiplicative; additive left rings).
Registration: the model drifts ~3-4 px/h after midnight (flexure), so each frame is shifted by its Polaris
offset (centroid minus prediction, running median over 15 frames); frames without Polaris are dropped. Cloud: frames whose >5 sigma pixel count is under 40% of the night's 90th percentile are dropped.
Model: ~/tmp/allcam/hqfs-cammodel-2026-11-12.json (scratch/allcam/fithqfs.py, 105 Gaia stars, 0.49 px).
Usage: hqfs_canvas.py [REF_UTC]   (default 2026-11-12T23:45:00)"""
import glob, json, os, sys, numpy as np, cv2
from multiprocessing import Pool
from datetime import datetime, timezone
from astropy.io import fits
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel, SIDEREAL_RAD_PER_S
OUT = os.path.expanduser("~/tmp/allcam/hqfs-canvas"); os.makedirs(OUT, exist_ok=True)
CAM = os.path.expanduser("~/tmp/allcam/hqfs-cammodel-2026-11-12.json")
X = sorted(glob.glob("/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-12/*/20261112T185923Z-*.fits.fz"), key=os.path.basename)
REF = datetime.fromisoformat((sys.argv[1] if len(sys.argv) > 1 else "2026-11-12T23:45:00") + "+00:00")
def binned(p):
    with fits.open(p) as h: d, hd = h[1].data.astype(np.float32), h[1].header
    H, W = d.shape; t = datetime.fromisoformat(hd["DATE-OBS"]); ex = float(hd["EXPTIME"])
    return d[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2).sum((1, 3)), t, ex
cm = CameraModel(CAM)
H, W = binned(X[0])[0].shape
# canvas: pole-centred equidistant disc reaching the farthest frame corner
yy, xx = np.mgrid[0:H:8, 0:W:8]; V = cm.unproject(xx.ravel(), yy.ravel())
R = np.arccos(np.clip(V @ cm.pole, -1, 1)).max() + np.radians(0.05)
N = int(2 * R * cm.f) + 1
q = dict(cm.p, az0=0.0, alt0=float(np.radians(cm.p["lat"])), roll=0.0, k=0.0, cx=N / 2, cy=N / 2,
         grid="hqfs_canvas.py: equidistant disc centred on the celestial pole at REF, native scale", shape=[N, N])
cv = CameraModel(q)
gy, gx = np.mgrid[0:N, 0:N].astype(np.float32); Vref = cv.unproject(gx, gy).reshape(-1, 3)
def rot(axis, ang):
    a = axis / np.linalg.norm(axis); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
from scipy.ndimage import uniform_filter
LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg); POL = SkyCoord(37.95456067 * u.deg, 89.26410897 * u.deg)
def sub(b):
    return b - BG * (np.median(b) / np.median(BG))
def level_n5(p):
    b, t, ex = binned(p); b = sub(b); b -= np.median(b); s = 1.4826 * np.median(np.abs(b))
    a = POL.transform_to(AltAz(obstime=Time(t) + ex / 2 * u.s, location=LOC, pressure=0)); al, az = a.alt.rad, a.az.rad
    px, py = (float(v) for v in cm.project(np.array([np.cos(al) * np.sin(az), np.cos(al) * np.cos(az), np.sin(al)])))
    dx = dy = np.nan
    x0, y0 = int(round(px)), int(round(py))
    if 45 <= x0 < W - 45 and 45 <= y0 < H - 45:
        c = uniform_filter(b[y0 - 45:y0 + 46, x0 - 45:x0 + 46], 7); j, i = np.unravel_index(np.argmax(c), c.shape)
        if c[j, i] > 30 * s and 8 <= i <= 82 and 8 <= j <= 82:
            w = np.clip(b[y0 - 45 + j - 8:y0 - 45 + j + 9, x0 - 45 + i - 8:x0 - 45 + i + 9], 0, None)
            yy, xx = np.mgrid[-8:9, -8:9]
            dx = x0 - 45 + i + (w * xx).sum() / w.sum() - px; dy = y0 - 45 + j + (w * yy).sum() / w.sum() - py
    return t.isoformat(), ex, float(s), int((b > 5 * s).sum()), float(dx), float(dy)
def chunk(ps):
    S = np.zeros((N, N)); Wt = np.zeros((N, N))
    for p, (ox, oy) in ps:
        b, t, ex = binned(p); b = sub(b); b -= np.median(b)
        dt = ((t - REF).total_seconds() + ex / 2)
        Vt = Vref @ rot(cm.pole, -SIDEREAL_RAD_PER_S * dt).T          # sky at REF -> where it is at t
        x, y = cm.project(Vt); x = x + ox; y = y + oy; mx = x.reshape(N, N).astype(np.float32); my = y.reshape(N, N).astype(np.float32)
        ok = np.isfinite(mx) & (Vt @ cm.b > 0).reshape(N, N)
        mx[~ok] = -1; my[~ok] = -1
        S += cv2.remap(b, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        Wt += cv2.remap(np.ones_like(b), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0.999
    return S, Wt
if __name__ == "__main__":
    print(f"{len(X)} frames; canvas {N} x {N} px, radius {np.degrees(R):.2f} deg, {206264.806 / cm.f:.2f}\"/px", flush=True)
    BG = np.median(np.stack([binned(p)[0] for p in X[:: max(1, len(X) // 80)]]), 0)
    with Pool(2) as P: st = P.map(level_n5, X, chunksize=20)
    n5 = np.array([s[3] for s in st]); keep = n5 >= 0.4 * np.percentile(n5, 90)
    from scipy.ndimage import median_filter
    dx = np.array([s[4] for s in st]); dy = np.array([s[5] for s in st]); has = np.isfinite(dx) & keep
    sx = np.full(len(X), np.nan); sy = np.full(len(X), np.nan)
    sx[has] = median_filter(dx[has], 15, mode="nearest"); sy[has] = median_filter(dy[has], 15, mode="nearest")
    keep = has
    for k in range(0, len(X), 300):
        if has[k]: print(f"  {st[k][0][11:19]} Polaris offset ({sx[k]:+.1f}, {sy[k]:+.1f}) px", flush=True)
    good = [(p, (sx[i], sy[i])) for i, p in enumerate(X) if keep[i]]
    print(f"clear: {len(good)} of {len(X)} frames (n5 >= {0.4 * np.percentile(n5, 90):.0f})", flush=True)
    with Pool(2) as P: parts = P.map(chunk, [good[i::8] for i in range(8)])
    S = sum(p[0] for p in parts); Wt = sum(p[1] for p in parts)
    mean = np.where(Wt > 0, S / np.maximum(Wt, 1), np.nan).astype(np.float32)
    hd = fits.Header(); hd["NIGHT"] = "2026-11-12"; hd["REFUTC"] = REF.isoformat(); hd["NFRAMES"] = len(good)
    hd["CAMMODEL"] = os.path.basename(CAM); hd["CANVAS"] = True
    fits.HDUList([fits.PrimaryHDU(mean, hd), fits.ImageHDU((Wt / Wt.max()).astype(np.float32), name="WEIGHT")]).writeto(f"{OUT}/derot-sky.fits", overwrite=True)
    json.dump(q, open(f"{OUT}/canvas-model.json", "w"), indent=1)
    json.dump([s for s, k in zip(st, keep) if k], open(f"{OUT}/derot-sky-frames.json", "w"))
    deep = Wt > 0.3 * Wt.max(); v = mean[deep]; sig = 1.4826 * np.median(np.abs(v - np.median(v)))
    print(f"-> {OUT}/derot-sky.fits  ({len(good)} frames; noise sigma {sig:.3f} ADU where >30% covered)")
