"""Radial profile about Peter's blob centre (2622,473), normalised to the 600-700 px annulus, per frame/night."""
import os, sys, glob, datetime, numpy as np
from astropy.io import fits
root = os.environ["BIGSTORE"] + "/astrocam-frames"
CX, CY = 2622, 473
edges = np.arange(0, 801, 50)
def load(p):
    with fits.open(p) as h:
        for x in h:
            if x.data is not None: d = x.data.astype(np.float64); break
    return d.mean(axis=0) if d.ndim == 3 and d.shape[0] <= 4 else d
yy, xx = np.mgrid[0:2592, 0:4608]; R = np.hypot(xx - CX, yy - CY)
sel = R < 800; Rs = R[sel]; idx = np.digitize(Rs, edges) - 1
print("r(px)      " + " ".join(f"{e:5d}" for e in edges[:-1]))
for n, picks in [(a.split(":")[0], a.split(":")[1:]) for a in sys.argv[1:]]:
    fs = sorted(glob.glob(f"{root}/{n}/??/*.fits.fz"), key=os.path.basename)
    for k in picks:
        p = fs[int(k) if int(k) >= 0 else len(fs) + int(k)]
        v = load(p)[sel]
        prof = np.array([np.median(v[idx == i]) for i in range(len(edges) - 1)])
        ref = np.median(v[(Rs > 600) & (Rs < 700)])
        t = datetime.datetime.fromtimestamp(int(os.path.basename(p).split(".")[0]) / 1000, datetime.UTC)
        print(t.strftime("%m-%d %H:%M"), " ".join(f"{x/ref:5.2f}" for x in prof), f" ref={ref:.0f}")
