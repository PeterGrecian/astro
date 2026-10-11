import glob, os, sys, numpy as np
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
from scipy.ndimage import maximum_filter
import check3
B = check3.BASE
for n in [f"2026-08-{d:02d}" for d in range(24, 32)] + [f"2026-09-{d:02d}" for d in range(1, 21)]:
    ps = sorted(glob.glob(f"{B}/{n}/v3w/01/*.fits.fz"))
    if not ps:
        print(n, "no 01h"); continue
    p = ps[len(ps) // 3]
    img, _ = check3.load(p)
    s = img[40:700, 100:1800]
    nz = 1.4826 * np.median(np.abs(s - np.median(s)))
    pk = (s == maximum_filter(s, 7)) & (s > 10 * nz)
    print(n, os.path.basename(p)[:13], "stars>10sig", int(pk.sum()), "noise", round(float(nz), 1), flush=True)
