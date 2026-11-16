#!/usr/bin/env python3
"""Polaris B, hqfs 2026-11-13, v3: angular differential imaging (ADI) with a fake-B injection test.
(v2 rdi1113b subtracted the same star's 1.5 s frames, which contain B at the same place: B cancels.)
Per cycle: P = registered mean of the 0.4 s run (A unsaturated). Each 12 s frame: registered cutout c,
saturation (dilated 1) -> NaN, normalised by k from c ~ k*P + b over r 13-42 px. Fake B = (k/480)*P
shifted to PA 350 (real B ~230), so it cannot overlap the real one. Reference for a cycle = median of
cycles >= DMIN deg of sky rotation away. Residuals rotated N-up/E-left (north = toward the pole from a
circle fit of A's track; east = against A's motion) and stacked. Scale 2.13-2.33 "/px (unsettled)."""
import os, csv, sys
os.environ["OMP_NUM_THREADS"] = "2"; os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi, optimize
from datetime import datetime
NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-11-13"
OUT = os.path.expanduser("~/tmp/polarisb-c"); os.makedirs(OUT, exist_ok=True)
H, SAT, FAKE_PA, RATIO = 45, 4000, 350.0, 1 / 480
DMIN = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
rows = list(csv.DictReader(open(f"{NIGHT}/brightness.csv")))
for r in rows:
    r["exp"] = round(float(r["exptime"]), 1); r["med"] = float(r["median"])
runs = []
for i, r in enumerate(rows):
    if runs and runs[-1]["exp"] == r["exp"] and i == runs[-1]["idx"][-1] + 1: runs[-1]["idx"].append(i)
    else: runs.append({"exp": r["exp"], "idx": [i]})
def load(i):
    with fits.open(rows[i]["filename"]) as h:
        return h[1].data.astype(np.float32), datetime.fromisoformat(h[1].header["DATE-OBS"]).timestamp()
def fixed(exp, n=41):
    c = [i for i, r in enumerate(rows) if r["exp"] == exp and r["med"] < 400]
    return np.median([load(i)[0] for i in c[::max(len(c) // n, 1)]], axis=0)
FP = {e: fixed(e) for e in (0.4, 12.0)}
W = np.array([[0.789, 1.172], [1.178, 0.86]]); WMAP = np.tile(W, (760, 1014))   # from rdi1113b
N = 2 * H + 1; yy, xx = np.indices((N, N)); rr = np.hypot(xx - H, yy - H)
def locate(a, g):
    s = ndi.gaussian_filter(a, 4); gx, gy = g; y0, x0 = max(gy - 60, 0), max(gx - 60, 0)
    sub = s[y0:gy + 61, x0:gx + 61]; y, x = np.unravel_index(np.argmax(sub), sub.shape); return x + x0, y + y0
def grab(a, sat, x, y):
    h = H + 6
    if not (h <= x < a.shape[1] - h and h <= y < a.shape[0] - h): return None
    c = a[y - h:y + h + 1, x - h:x + h + 1]; cs = sat[y - h:y + h + 1, x - h:x + h + 1]
    b = np.median(np.r_[c[0], c[-1], c[:, 0], c[:, -1]]); d = np.clip(c - b, 0, None); w = d * (d > 0.15 * d.max())
    Y, X = np.indices(c.shape); cx, cy = (w * X).sum() / w.sum(), (w * Y).sum() / w.sum()
    sh = (h - cy, h - cx)
    return (ndi.shift(c - b, sh, order=3)[6:-6, 6:-6], ndi.shift(cs.astype(float), sh, order=1)[6:-6, 6:-6] > 0.01,
            x - h + cx, y - h + cy)
# pass 1: per cycle P (0.4 s) and the 12 s cutouts
guess = (1718, 1311); cyc = []
for k, run in enumerate(runs):
    if run["exp"] != 0.4: continue
    nxt = next((r2 for r2 in runs[k + 1:k + 4] if r2["exp"] == 12.0), None)
    if nxt is None or np.median([rows[i]["med"] for i in nxt["idx"]]) > 330: continue
    Ps = []
    for i in run["idx"]:
        a, _ = load(i); a = (a - FP[0.4]) / WMAP
        if not Ps:    # first frame of the run: Polaris is the brightest thing in the field
            sm = ndi.gaussian_filter(a, 4); y0, x0 = np.unravel_index(np.argmax(sm), sm.shape); guess = (int(x0), int(y0))
        x, y = locate(a, guess); g = grab(a, a * 0 > 1, x, y)
        if g is None: break
        Ps.append(g[0]); guess = (x, y)
    if len(Ps) < 10: continue
    a, _ = load(nxt["idx"][0]); sat = a >= SAT; x, y = locate((a - FP[12.0]) / WMAP, guess)
    if sat[y - 15:y + 16, x - 15:x + 16].sum() < 60: continue      # not Polaris
    P = np.mean(Ps, axis=0); Cs = []
    for i in nxt["idx"]:
        a, t = load(i); sat = a >= SAT; a = (a - FP[12.0]) / WMAP; x, y = locate(a, guess); g = grab(a, sat, x, y)
        if g is None: break
        guess = (x, y); c, cs, ax, ay = g; bad = ndi.binary_dilation(cs, iterations=1)
        m = (~bad) & (rr > 13) & (rr < 42)
        k_, b_ = np.linalg.lstsq(np.c_[P[m], np.ones(m.sum())], c[m], rcond=None)[0]
        Cs.append((c - b_, bad, k_, t, ax, ay))
    cyc.append((P, Cs)); print(f"cycle {rows[run['idx'][0]]['iso_utc'][11:16]} n12 {len(Cs)} k {np.median([q[2] for q in Cs]):.1f} (expect 30)", flush=True)
# geometry
t = np.array([q[3] for _, Cs in cyc for q in Cs]); ax = np.array([q[4] for _, Cs in cyc for q in Cs]); ay = np.array([q[5] for _, Cs in cyc for q in Cs])
xc, yc, R = optimize.least_squares(lambda p: np.hypot(ax - p[0], ay - p[1]) - p[2], [ax.mean(), ay.mean() + 800, 1000]).x
vx, vy = ndi.uniform_filter1d(np.gradient(ax, t), 41), ndi.uniform_filter1d(np.gradient(ay, t), 41)
nx, ny = xc - ax, yc - ay; n = np.hypot(nx, ny); nx, ny = nx / n, ny / n
ex, ey = -vx, -vy; n = np.hypot(ex, ey); ex, ey = ex / n, ey / n
theta = np.degrees(np.unwrap(np.arctan2(ny, nx)))       # camera angle of north at A
print(f"pole ({xc:.0f},{yc:.0f}) R {R:.0f} px; rotation span {theta.max()-theta.min():.0f} deg; frames {len(t)}", flush=True)
def sky_to_cam(pa, r, j):    # offset (dx, dy) in camera px of a point at PA, r from A
    E, Nn = r * np.sin(np.radians(pa)), r * np.cos(np.radians(pa))
    return E * ex[j] + Nn * nx[j], E * ey[j] + Nn * ny[j]
# normalised frames, with and without fake B
F, Ffk, M, cid = [], [], [], []
j = 0
for ci, (P, Cs) in enumerate(cyc):
    for c, bad, k_, *_ in Cs:
        dx, dy = sky_to_cam(FAKE_PA, 8.5, j)
        fake = ndi.shift(P, (dy, dx), order=3) * k_ * RATIO
        f = c / k_; f[bad] = np.nan; F.append(f)
        g = (c + fake) / k_; g[bad] = np.nan; Ffk.append(g); cid.append(ci); j += 1
F, Ffk, cid = np.array(F, np.float32), np.array(Ffk, np.float32), np.array(cid)
cth = np.array([theta[cid == ci].mean() for ci in range(len(cyc))])
cols, rws = np.meshgrid(np.arange(N), np.arange(N)); Eo, No = H - cols, H - rws
def adi(FR):
    acc = np.zeros((N, N)); w = np.zeros((N, N)); used = 0
    for ci in range(len(cyc)):
        far = np.abs(cth - cth[ci]) >= DMIN
        if far.sum() < 3: continue
        ref = np.nanmedian(FR[np.isin(cid, np.where(far)[0])], axis=0)
        for jj in np.where(cid == ci)[0]:
            d = FR[jj] - ref; m = np.isfinite(d).astype(float); d = np.nan_to_num(d)
            X = H + Eo * ex[jj] + No * nx[jj]; Y = H + Eo * ey[jj] + No * ny[jj]
            acc += ndi.map_coordinates(d, [Y, X], order=1); w += ndi.map_coordinates(m, [Y, X], order=1); used += 1
    return np.where(w > 0.3 * w.max(), acc / np.maximum(w, 1e-9), np.nan), used
pa_map = np.degrees(np.arctan2(Eo, No)) % 360
def scan(S, r0, ap=2.5):
    out = []
    for p in range(0, 360, 10):
        cx, cy = H - r0 * np.sin(np.radians(p)), H - r0 * np.cos(np.radians(p))
        m = (np.hypot(cols - cx, rws - cy) < ap) & np.isfinite(S)
        out.append(np.nanmean(S[m]) if m.sum() > 4 else np.nan)
    return np.array(out)
for tag, FR in (("real", F), ("fake350", Ffk)):
    S, used = adi(FR); np.save(f"{OUT}/S_{tag}_d{DMIN:.0f}.npy", S)
    print(f"== {tag}: DMIN {DMIN} frames used {used}  (units: ADU of a 0.4 s frame; aperture mean r<2.5 px)")
    for r0 in (7.5, 8.5, 9.5, 10.5, 11.5, 13):
        sc = scan(S, r0); ok = np.isfinite(sc)
        line = " ".join("    ." if not o else f"{v:+5.1f}" for v, o in zip(sc, ok))
        print(f" r{r0:4.1f} rms {np.nanstd(sc):5.1f} | {line}")
    print("        PA:      " + " ".join(f"{p:5d}" for p in range(0, 360, 10)))
# fake-B expected peak in same units: P peak/480
Pm = np.mean([P for P, _ in cyc], axis=0); m = rr < 2.5
print(f"fake B: peak {Pm.max()*RATIO:.2f}, aperture mean {Pm[m].mean()*RATIO:.2f} (same units); A's P peak {Pm.max():.0f}")
