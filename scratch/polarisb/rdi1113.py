#!/usr/bin/env python3
"""Polaris B from hqfs 2026-11-13 by reference subtraction (RDI) against the same star's 1.5 s frames.
Per ladder cycle: R = registered mean of the 1.5 s run (core mostly unsaturated); each following 12 s
frame F is fitted as s*shift(R)+b over unsaturated pixels, residual D = F - fit. D is rotated to
north-up / east-left (pole from a circle fit to A's track) and stacked. Works in 2x2 superpixels
(binned raw 2.13"/px -> 4.26"/sp), so B (18.2" at PA ~230) is expected ~4.3 sp from A.
Outputs ~/tmp/polarisb/: stack.npy, weight.npy, nostack.npy (not derotated), track.csv, log."""
import os, csv, sys, json
os.environ["OMP_NUM_THREADS"] = "2"; os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi, optimize
NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-11-13"
OUT = os.path.expanduser("~/tmp/polarisb"); os.makedirs(OUT, exist_ok=True)
H = 30                      # cutout half-size, superpixels
SAT = 4000
rows = list(csv.DictReader(open(f"{NIGHT}/brightness.csv")))
for r in rows:
    r["exp"] = round(float(r["exptime"]), 1); r["med"] = float(r["median"])
# runs of equal exposure
runs = []
for i, r in enumerate(rows):
    if runs and runs[-1]["exp"] == r["exp"] and i == runs[-1]["idx"][-1] + 1:
        runs[-1]["idx"].append(i)
    else:
        runs.append({"exp": r["exp"], "idx": [i]})
print("runs", len(runs), [(x["exp"], len(x["idx"])) for x in runs[:8]], flush=True)

def load(i):
    with fits.open(rows[i]["filename"]) as h:
        a = h[1].data.astype(np.float32); t = h[1].header["DATE-OBS"]
    sp = a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]
    sat = ((a[0::2, 0::2] >= SAT) | (a[0::2, 1::2] >= SAT) | (a[1::2, 0::2] >= SAT) | (a[1::2, 1::2] >= SAT))
    return sp, sat, t

def tsec(t):
    from datetime import datetime
    return datetime.fromisoformat(t).timestamp()

# fixed pattern per exposure class: median of frames sampled through the clear part
def fixed(exp, n=41):
    cand = [i for i, r in enumerate(rows) if r["exp"] == exp and r["med"] < 400]
    pick = cand[::max(len(cand) // n, 1)]
    return np.median([load(i)[0] for i in pick], axis=0)
FP = {e: fixed(e) for e in (1.5, 12.0)}
print("fixed patterns built", flush=True)

def locate(sp, guess=None):
    s = ndi.gaussian_filter(sp, 2)
    if guess is None:
        y, x = np.unravel_index(np.argmax(s), s.shape)
    else:
        gx, gy = guess; y0, x0 = max(gy - 40, 0), max(gx - 40, 0)
        sub = s[y0:gy + 41, x0:gx + 41]; y, x = np.unravel_index(np.argmax(sub), sub.shape); y += y0; x += x0
    return int(x), int(y)

def cut(img, x, y, h=H + 6):
    if not (h <= x < img.shape[1] - h and h <= y < img.shape[0] - h):
        return None
    return img[y - h:y + h + 1, x - h:x + h + 1]

def centroid(c, sat):
    b = np.median(np.r_[c[0], c[-1], c[:, 0], c[:, -1]])
    d = np.clip(c - b, 0, None); w = d * (d > 0.15 * d.max())
    yy, xx = np.indices(c.shape)
    return (w * xx).sum() / w.sum(), (w * yy).sum() / w.sum(), b

N = 2 * H + 1
yy, xx = np.indices((N, N)); rr = np.hypot(xx - H, yy - H)
track, Ds = [], []
nostack = np.zeros((N, N)); nowt = np.zeros((N, N))
for k, run in enumerate(runs):
    if run["exp"] != 1.5:
        continue
    nxt = next((r2 for r2 in runs[k + 1:k + 3] if r2["exp"] == 12.0), None)
    if nxt is None:
        continue
    if np.median([rows[i]["med"] for i in nxt["idx"]]) > 330:
        continue
    # reference
    refs, guess = [], None
    for i in run["idx"]:
        sp, sat, t = load(i); sp = sp - FP[1.5]
        x, y = locate(sp, guess); guess = (x, y)
        c = cut(sp, x, y); cs = cut(sat, x, y)
        if c is None:
            break
        cx, cy, b = centroid(c, cs)
        sh = (H + 6 - cy, H + 6 - cx)
        refs.append((ndi.shift(c - b, sh, order=3)[6:-6, 6:-6], ndi.shift(cs.astype(float), sh, order=1)[6:-6, 6:-6] > 0.01))
    if len(refs) < 10:
        continue
    R = np.mean([r[0] for r in refs], axis=0); Rsat = np.any([r[1] for r in refs], axis=0)
    for i in nxt["idx"]:
        sp, sat, t = load(i); sp = sp - FP[12.0]
        x, y = locate(sp, guess); guess = (x, y)
        c = cut(sp, x, y); cs = cut(sat, x, y)
        if c is None:
            break
        cx, cy, b0 = centroid(c, cs)
        c0 = ndi.shift(c - b0, (H + 6 - cy, H + 6 - cx), order=3)[6:-6, 6:-6]
        s0 = ndi.shift(cs.astype(float), (H + 6 - cy, H + 6 - cx), order=1)[6:-6, 6:-6] > 0.01
        bad = ndi.binary_dilation(s0 | Rsat, iterations=1)
        fitm = (~bad) & (rr > 2) & (rr < 22)
        def resid(p):
            dx, dy, s, b = p
            m = ndi.shift(R, (dy, dx), order=3)
            return (c0 - s * m - b)[fitm]
        p = optimize.least_squares(resid, [0, 0, 8.0, 0], loss="soft_l1", f_scale=50).x
        D = c0 - p[2] * ndi.shift(R, (p[1], p[0]), order=3) - p[3]
        D[bad] = np.nan
        ax, ay = x - H - 6 + cx + p[0], y - H - 6 + cy + p[1]   # A in full superpixel coords (approx)
        track.append((i, tsec(t), ax, ay, p[2], p[3], int(s0.sum()), float(np.nanstd(D[(rr > 8) & (rr < 20)]))))
        Ds.append(D.astype(np.float32))
        ok = np.isfinite(D); nostack[ok] += D[ok]; nowt[ok] += 1
    print(f"cycle {rows[run['idx'][0]]['iso_utc'][11:16]} refs {len(refs)} n12 {len(nxt['idx'])} last s {p[2]:.2f} sat {int(s0.sum())} A ({ax:.0f},{ay:.0f})", flush=True)

T = np.array(track)
np.save(f"{OUT}/Ds.npy", np.array(Ds)); np.save(f"{OUT}/track.npy", T)
np.save(f"{OUT}/nostack.npy", nostack / np.maximum(nowt, 1))
print("frames", len(T), flush=True)
