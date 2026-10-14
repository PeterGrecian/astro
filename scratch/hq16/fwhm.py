"""Cross-trail FWHM of stars on eclipticam-hq16 frames (night 2026-10-13, epoch 1).

60 s frames from a fixed camera: stars are trails ~22 binned px long, so the
focus measure is the width ACROSS the trail. Per frame: sum 2x2 RGGB to the
binned grid (39.8"/px), subtract a smooth background, segment, keep isolated
unsaturated trails, rotate each cutout to its trail axis, collapse along the
middle of the trail and fit a Gaussian across it. Also on the green photosites
alone (19.9"/photosite, diagonal sampling) for the bright ones.
"""
import os, sys, json, glob
import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from scipy.ndimage import rotate, gaussian_filter
from scipy.optimize import curve_fit

ROOT = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/eclipticam-frames/night/2026-10-13/hq16"
SCALE = 39.8  # arcsec per binned pixel
files = sorted(glob.glob(ROOT + "/*/*.fits.fz"))
step = int(sys.argv[1]) if len(sys.argv) > 1 else 10
files = files[::step]

def g(x, a, mu, s, c):
    return a * np.exp(-0.5 * ((x - mu) / s) ** 2) + c

out = []
for f in files:
    with fits.open(f) as h:
        d = h[1].data.astype(np.float32) - 256.0
        t = h[1].header["DATE-OBS"]
    b = d[0::2, 0::2] + d[0::2, 1::2] + d[1::2, 0::2] + d[1::2, 1::2]
    sat = 4 * (4095 - 256) * 0.9
    bkg = Background2D(b, (64, 64), filter_size=(3, 3), bkg_estimator=MedianBackground())
    r = b - bkg.background
    _, _, sd = sigma_clipped_stats(r, sigma=3)
    seg = detect_sources(gaussian_filter(r, 1.0), 5 * sd, npixels=20)
    if seg is None:
        out.append(dict(t=t, n=0)); continue
    cat = SourceCatalog(r, seg)
    H, W = r.shape
    rows = []
    for s in cat:
        L, w = float(s.semimajor_sigma.value), float(s.semiminor_sigma.value)
        x, y = float(s.xcentroid), float(s.ycentroid)
        if not (30 < x < W - 30 and 30 < y < H - 30): continue
        if s.max_value > sat or L < 2 * w: continue
        th = float(s.orientation.value)  # deg, from +x
        half = int(max(3 * L, 15))
        cut = r[int(y) - half:int(y) + half + 1, int(x) - half:int(x) + half + 1]
        if cut.shape != (2 * half + 1, 2 * half + 1): continue
        rc = rotate(cut, th, reshape=False, order=1)  # trail now along x
        c = half
        Lh = max(int(1.0 * L), 2)
        prof = rc[:, c - Lh:c + Lh + 1].mean(axis=1)
        yy = np.arange(len(prof))
        try:
            p, _ = curve_fit(g, yy, prof, p0=[prof.max(), c, 1.0, 0.0])
        except Exception:
            continue
        if not (0.3 < abs(p[2]) < 6 and abs(p[1] - c) < 3 and p[0] > 0): continue
        snr = p[0] / (sd / np.sqrt(2 * Lh + 1))
        if snr < 20: continue
        rows.append((x, y, 2.3548 * abs(p[2]), 2.3548 * L, th, snr))
    rows = np.array(rows) if rows else np.zeros((0, 6))
    def zone(m):
        v = rows[m, 2]
        return (float(np.median(v)), int(m.sum())) if m.sum() >= 3 else (None, int(m.sum()))
    if len(rows):
        rr = np.hypot((rows[:, 0] - W / 2) / (W / 2), (rows[:, 1] - H / 2) / (H / 2))
        rec = dict(t=t, n=len(rows), fwhm=float(np.median(rows[:, 2])),
                   centre=zone(rr < 0.4), mid=zone((rr >= 0.4) & (rr < 0.8)), edge=zone(rr >= 0.8),
                   trail=float(np.median(rows[:, 3])), theta=float(np.median(rows[:, 4])),
                   sky=float(np.median(bkg.background)))
        # quadrants for tilt
        for nm, m in [("TL", (rows[:,0] < W/2) & (rows[:,1] < H/2)), ("TR", (rows[:,0] >= W/2) & (rows[:,1] < H/2)),
                      ("BL", (rows[:,0] < W/2) & (rows[:,1] >= H/2)), ("BR", (rows[:,0] >= W/2) & (rows[:,1] >= H/2))]:
            rec[nm] = zone(m & (rr >= 0.5))
    else:
        rec = dict(t=t, n=0)
    out.append(rec)
    print(json.dumps(rec), flush=True)
    if f == files[len(files) // 2]:
        np.save(os.path.expanduser("~/tmp/hq16-fwhm-stars.npy"), rows)
json.dump(out, open(os.path.expanduser("~/tmp/hq16-fwhm.json"), "w"), indent=1)
