"""hqfs plate solve, second try: stored frames are 2028x1520 already; sum 10 consecutive frames at full
stored resolution, subtract a wide median (fixed pattern), hint the pole (position 6 points ~at it)."""
import glob, os, subprocess, numpy as np
from astropy.io import fits
OUT = os.path.expanduser("~/tmp/allcam/solve")
X = sorted(glob.glob("/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-12/*/20261112T185923Z-*.fits.fz"), key=os.path.basename)
i = 300
ld = lambda p: fits.getdata(p, 1).astype(np.float32)
bg = np.median(np.stack([ld(p) for p in X[i - 200:i + 200:40]]), 0)
img = np.sum([ld(p) - bg for p in X[i:i + 10]], 0)
f = f"{OUT}/hqfs2.fits"; fits.writeto(f, img, overwrite=True)
import shutil
for tag, ds, lo, hi in (("hqfs3", 4, 1.5, 3.0), ("hqfs4", 8, 1.5, 3.0), ("hqfs5", 4, 0.5, 6.0)):
    shutil.copy(f, f"{OUT}/{tag}.fits")
    r = subprocess.run(["solve-field", "--overwrite", "--no-plots", "--downsample", str(ds), "--scale-units", "arcsecperpix",
                        "--scale-low", str(lo), "--scale-high", str(hi), "--ra", "37.95", "--dec", "89.26", "--radius", "5",
                        "--cpulimit", "120", "--dir", OUT, f"{OUT}/{tag}.fits"], capture_output=True, text=True)
    print(tag, "SOLVED" if os.path.exists(f"{OUT}/{tag}.solved") else "failed",
          [l for l in r.stdout.splitlines() if "Field center" in l or "Field size" in l or "rotation" in l or "pixel scale" in l])
print(X[i], fits.getdata(f"{OUT}/hqfs2.axy").shape if os.path.exists(f"{OUT}/hqfs2.axy") else "")
