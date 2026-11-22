"""Plate-solve one hqfs and one hq16 frame from night 2026-11-12 (astrometry.net, tycho2 index).
hqfs: median of 9 consecutive frames removes fixed pattern; then frame minus median of a wider set."""
import glob, os, subprocess, sys, numpy as np
from astropy.io import fits
sys.path.insert(0, "/home/peter/astro")
OUT = os.path.expanduser("~/tmp/allcam/solve"); os.makedirs(OUT, exist_ok=True)
def binned(p):
    d = fits.getdata(p, 1).astype(np.float32); H, W = d.shape
    return d[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2).sum((1, 3))
def solve(tag, img, lo, hi, extra=()):
    f = f"{OUT}/{tag}.fits"; fits.writeto(f, img.astype(np.float32), overwrite=True)
    r = subprocess.run(["solve-field", "--overwrite", "--no-plots", "--downsample", "2", "--scale-units", "arcsecperpix",
                        "--scale-low", str(lo), "--scale-high", str(hi), "--cpulimit", "120", "--dir", OUT, f, *extra],
                       capture_output=True, text=True)
    ok = os.path.exists(f"{OUT}/{tag}.solved")
    print(tag, "SOLVED" if ok else "failed", [l for l in r.stdout.splitlines() if "Field center" in l or "Field size" in l or "rotation" in l])
X = sorted(glob.glob("/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-12/*/20261112T185923Z-*.fits.fz"))
i = 1500; stk = np.stack([binned(p) for p in X[i - 40:i + 40:8]]); bg = np.median(stk, 0)
img = np.median(np.stack([binned(p) for p in X[i:i + 5]]), 0) - bg  # 5-frame median minus wider median (stars move)
solve("hqfs", img, 2.0, 8.0)
H = sorted(glob.glob("/mnt/bigstore/astro-data/eclipticam-frames/night/2026-11-12/hq16/0[0-1]/*.fits.fz"))
j = len(H) // 2; stk = np.stack([binned(p) for p in H[j - 20:j + 20:4]]); bg = np.median(stk, 0)
solve("hq16", binned(H[j]) - bg, 30, 50)
print("frames", X[i], H[j])
