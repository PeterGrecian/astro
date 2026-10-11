import glob, os, sys, json, numpy as np
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import check3
from scipy.ndimage import maximum_filter
from astropy.coordinates import get_body
from astropy.time import Time
p = dict(check3.P, az0=np.radians(200.48), alt0=np.radians(31.86), roll=np.radians(3.59), f=976.0)
cm = check3.model(p)
for d in range(1, 23):
    n = f"2026-08-{d:02d}"
    ps = sorted(glob.glob(f"{check3.BASE}/{n}/v3w/02/*.fits.fz"))
    if not ps:
        print(n, "no 02h"); continue
    pth = ps[len(ps) // 2]
    t = datetime.fromtimestamp(int(os.path.basename(pth)[:13]) / 1000, timezone.utc) + timedelta(seconds=30)
    x, y = cm.project(check3.enu_of(get_body("saturn", Time(t), check3.LOC), t))
    img, _ = check3.load(pth)
    s = img[40:700, 100:1800]
    nz = 1.4826 * np.median(np.abs(s - np.median(s)))
    pk = (s == maximum_filter(s, 7)) & (s > 10 * nz)
    print(n, f"{t:%H:%M}", "stars", int(pk.sum()), f"Saturn pred ({x[0]:.0f},{y[0]:.0f})", flush=True)
