"""For each night, the frame where the sword should sit at the 10-09 reference pixel: exposure, sky, star count."""
import glob, os, datetime as dt
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
BASE = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data")
REF_MS, REF_NIGHT = 1791601980645, dt.date(2026, 10, 9)
CX, CY = 1016 // 2, 1053 // 2
for k in range(-25, 2):
    night = REF_NIGHT + dt.timedelta(days=k)
    files = glob.glob(f"{BASE}/eclipticam-frames/night/{night}/*/*/*.fits.fz")
    if not files:
        print(night, "no frames"); continue
    t = REF_MS + k * 86164091
    eps = np.array([int(os.path.basename(p).split(".")[0]) for p in files])
    i = int(np.argmin(np.abs(eps - t)))
    off = (eps[i] - t) / 1000
    h = fits.open(files[i])[1]
    d = h.data.astype(np.float32) - h.header.get("BLACKLVL", 64)
    lum = d[0::2, 0::2] + d[1::2, 1::2] + 0.5 * (d[0::2, 1::2] + d[1::2, 0::2])
    sub = lum[CY - 150:CY + 150, CX - 150:CX + 150]
    sub = sub - ndi.median_filter(sub, 31)
    sm = ndi.gaussian_filter(sub, 1.5)
    nz = 1.4826 * np.median(np.abs(sm - np.median(sm)))
    n = ndi.label(sm > 8 * nz)[1]
    pk = sm[150 - 30:150 + 30, 150 - 30:150 + 30].max() / nz
    print(night, files[i].split("/night/")[1].split("/")[1], f"dt={off:+6.0f}s",
          "exp", h.header.get("EXPTIME"), "mean", round(float(h.header.get("MEAN", -1)), 1),
          "stars", n, "swordpk", round(float(pk), 1), "n_frames", len(files), flush=True)
