#!/usr/bin/env python3
"""Identify the rings in the fshq night still: match against Tycho-2 about the pole, rotation unknown."""
import csv, io, os, urllib.parse, urllib.request
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "1"
os.nice(15)
import numpy as np
from scipy import ndimage as ndi
from astropy.coordinates import SkyCoord, FK5
import astropy.units as u

OUT = os.path.expanduser("~/tmp/fshq-survey")
img = np.load(f"{OUT}/night_still_raw_v2.npy"); fr = np.load(f"{OUT}/night_still_frames_v2.npy")
good = fr >= 60
l = np.mean([p / (1.4826 * np.median(np.abs(p[good]))) for p in img], axis=0)
raw = img.mean(axis=0)
sm = ndi.gaussian_filter(l, 2)
s = 1.4826 * np.median(np.abs(sm[good]))
lab, n = ndi.label((sm > 6 * s) & good)
idx = range(1, n + 1)
fl = ndi.sum(np.clip(raw, 0, None), lab, idx)
cm = np.array(ndi.center_of_mass(np.clip(raw, 0, None), lab, idx))
area = ndi.sum(lab > 0, lab, idx)
keep = (area >= 30) & (area < 2000)
print("objects", n, "kept", keep.sum())
ord_ = np.argsort(-fl[keep])
oy, ox, of, oa = cm[keep][ord_, 0], cm[keep][ord_, 1], fl[keep][ord_], area[keep][ord_]

# pole on the canvas, recomputed as in night_still.py
PX, PY = -502, -1763
H, Wd = 760, 1014
W_ = np.radians(15.0411 * 3 / 3600)
T0 = 7449 - 1
fc = np.array([(Wd - 1) / 2 - PX, (H - 1) / 2 - PY])
spin = -np.pi / 2 - np.arctan2(fc[1], fc[0])
cs = []
for nn in range(1, 14802, 100):
    th = W_ * (nn - 7449) + spin
    c, si = np.cos(th), np.sin(th)
    for x, y in ((0, 0), (Wd - 1, 0), (0, H - 1), (Wd - 1, H - 1)):
        dx, dy = x - PX, y - PY
        cs.append((c * dx - si * dy, si * dx + c * dy))
cs = np.array(cs)
x0, y0 = cs.min(axis=0); x1, y1 = cs.max(axis=0)
scale = (x1 - x0 + 1) / 2000
pole = np.array([-x0 / scale, -y0 / scale])
pxscale = scale * 4.26 / 3600       # degrees per output px, theoretical
print("pole on canvas", pole.round(1), "deg/px", round(pxscale, 5), "canvas height", int((y1 - y0 + 1) / scale) + 1)

# catalogue
txt = open(f"{OUT}/tyc.tsv").read()      # fetched on ora: VizieR times out from muppet
rows = [r for r in csv.reader(io.StringIO(txt), delimiter="\t") if len(r) >= 9 and r[0].strip().isdigit()]
print("catalogue stars", len(rows))
ra = np.array([float(r[3]) for r in rows]); de = np.array([float(r[4]) for r in rows])
pmra = np.array([float(r[5] or 0) for r in rows]); pmde = np.array([float(r[6] or 0) for r in rows])
vt = np.array([float(r[7] or 99) for r in rows])
yrs = 26.83
de2 = de + pmde * yrs / 3.6e6
ra2 = ra + pmra * yrs / 3.6e6 / np.maximum(np.cos(np.radians(de)), 0.01)
c = SkyCoord(ra2 * u.deg, de2 * u.deg, frame=FK5(equinox="J2000")).transform_to(FK5(equinox="J2026.83"))
rho = 90 - c.dec.deg
ang = np.radians(c.ra.deg)
keepc = rho < 4.0
rho, ang, vt, rows, ra_now, dec_now = rho[keepc], ang[keepc], vt[keepc], [r for r, k in zip(rows, keepc) if k], c.ra.deg[keepc], c.dec.deg[keepc]
order = np.argsort(vt)
rho, ang, vt, ra_now, dec_now = rho[order], ang[order], vt[order], ra_now[order], dec_now[order]
rows = [rows[i] for i in order]
print("within 4 deg, by VT:", np.round(vt[:12], 2), "rho", np.round(rho[:12], 2))

# search rotation and handedness
N = min(40, len(ox))
rx, ry = (ox[:N] - pole[0]) * pxscale, (oy[:N] - pole[1]) * pxscale
TOL = 0.06   # deg, allows for a pole error of ~15 px
cat = min(250, len(rho))
best = []
for parity in (1, -1):
    for t in np.radians(np.arange(0, 360, 0.25)):
        cx = rho[:cat] * np.cos(parity * ang[:cat] + t)
        cy = rho[:cat] * np.sin(parity * ang[:cat] + t)
        d = np.hypot(rx[:, None] - cx, ry[:, None] - cy)
        hits = (d.min(axis=1) < TOL).sum()
        best.append((hits, parity, t))
hits = np.array([b[0] for b in best])
top = sorted(best, key=lambda b: -b[0])[:5]
print("match score: best", [(b[0], b[1], round(float(np.degrees(b[2])), 2)) for b in top], "median", np.median(hits), "99th pct", np.percentile(hits, 99))
_, parity, t = top[0]
print("handedness", parity)

# refine: similarity fit, iterating (scale, rotation, shift)
A = rho * np.cos(parity * ang + t); B = rho * np.sin(parity * ang + t)
tx, ty = 0.0, 0.0; k = 1.0; a = 0.0
X, Y = (ox - pole[0]) * pxscale, (oy - pole[1]) * pxscale
for it in range(6):
    px_ = k * (np.cos(a) * A - np.sin(a) * B) + tx
    py_ = k * (np.sin(a) * A + np.cos(a) * B) + ty
    d = np.hypot(X[:, None] - px_, Y[:, None] - py_)
    j = d.argmin(axis=1); dd = d.min(axis=1)
    tol = TOL if it < 2 else 0.04
    m = dd < tol
    if m.sum() < 4:
        break
    M = []; v = []
    for i in np.nonzero(m)[0]:
        ja = j[i]
        M += [[A[ja], -B[ja], 1, 0], [B[ja], A[ja], 0, 1]]
        v += [X[i], Y[i]]
    sol = np.linalg.lstsq(np.array(M), np.array(v), rcond=None)[0]
    k = np.hypot(sol[0], sol[1]); a = np.arctan2(sol[1], sol[0]); tx, ty = sol[2], sol[3]
print(f"fit: {m.sum()} matches, scale factor {k:.4f} (focal length {300 / k:.1f} mm if the rest is right), rotation {np.degrees(a):.2f}, pole offset {tx / pxscale:.1f},{ty / pxscale:.1f} px, rms {np.std(dd[m]) / pxscale:.1f} px")
print("rank  x    y  flux  area   TYC             VT    dist_from_pole  ra_now dec_now  sep_px")
for i in range(min(45, len(ox))):
    ja = j[i]
    mark = "" if dd[i] < 0.04 else "  (no match)"
    print(i + 1, f"{ox[i]:.0f} {oy[i]:.0f} {of[i]:.0f} {oa[i]:.0f}", f"{rows[ja][0]}-{rows[ja][1]}-{rows[ja][2]}", f"{vt[ja]:.2f} {rho[ja]:.2f} {ra_now[ja]:.2f} {dec_now[ja]:.3f} {dd[i] / pxscale:.1f}" + mark)
# false-match test: bright catalogue stars inside the arch with no object
np.savez(f"{OUT}/identify.npz", ox=ox, oy=oy, of=of, A=A, B=B, k=k, a=a, tx=tx, ty=ty, vt=vt, pole=pole, pxscale=pxscale)
