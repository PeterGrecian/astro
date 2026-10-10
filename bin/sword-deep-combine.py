#!/usr/bin/env python3
"""Combine per-night sword stacks onto the 10-09 grid: star-matched affine, inverse-variance weights."""
import glob, sys
import numpy as np
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

ROOT = "/mnt/muppet/bigstore/eclipticam-frames/night"
REF = "2026-10-09"
NAME = sys.argv[2] if len(sys.argv) > 2 else "sword-stack"
SUF = sys.argv[3] if len(sys.argv) > 3 else ""          # "_eq": the equal-weight means saved beside the weighted ones
files = sorted(glob.glob(f"{ROOT}/*/{NAME}.npz"))

def lum(z): return z["R" + SUF] + z["G" + SUF] + z["B" + SUF]

def flat(im): return im - ndi.median_filter(im, 41)

def noise(im):
    f = flat(im)[12:-12, 12:-12]                      # off the edges, where the night-to-night shifts pad
    return 1.4826 * np.median(np.abs(f - np.median(f)))

def stars(im):
    f = flat(im); sm = ndi.gaussian_filter(f, 1.5)
    lab, n = ndi.label(sm > 10 * noise(im))
    idx = np.arange(1, n + 1)
    c = np.array(ndi.center_of_mass(np.clip(f, 0, None), lab, idx))[:, ::-1]
    fl = ndi.sum(f, lab, idx)
    return c[np.argsort(-fl)][:40]

def fit_aff(src, dst):
    X = np.column_stack([src, np.ones(len(src))])
    return np.linalg.lstsq(X, dst, rcond=None)[0].T

ref = np.load(f"{ROOT}/{REF}/{NAME}.npz", allow_pickle=True)
Lr = lum(ref); sr = stars(Lr)
fr0 = flat(Lr); n0r = noise(Lr)
lab0, nl = ndi.label(ndi.binary_dilation(ndi.gaussian_filter(fr0, 1.5) > 10 * n0r, iterations=3))
idx0 = np.arange(1, nl + 1); f0 = ndi.sum(fr0, lab0, idx0); Ts = []
hw = Lr.shape[0]; yy, xx = np.mgrid[0:hw, 0:hw].astype(float)
W = []; rows = []
for f in files:
    night = f.split("/")[-2]; z = np.load(f, allow_pickle=True)
    L = lum(z); n = int(z["n"])
    if n < 10:
        rows.append((night, n, "skip: too few frames")); continue
    s = stars(L)
    if night == REF:
        A = np.array([[1.0, 0, 0], [0, 1, 0]]); res = 0.0
    else:
        # coarse shift by cross-correlation (the camera's aim creeps ~0.5 superpixel/day), then affine on star matches
        def cl(im): f = flat(im); return np.clip(f, 0, np.percentile(f, 99.9))
        c = np.real(np.fft.ifft2(np.conj(np.fft.fft2(cl(Lr))) * np.fft.fft2(cl(L))))
        dy, dx = np.unravel_index(c.argmax(), c.shape)
        dx = dx - hw if dx > hw // 2 else dx; dy = dy - hw if dy > hw // 2 else dy
        d = s[:, None, :] - (sr[None, :, :] + (dx, dy))
        dist = np.hypot(*d.transpose(2, 0, 1))
        j = dist.argmin(1); ok = dist[np.arange(len(s)), j] < 6
        if ok.sum() < 6:
            rows.append((night, n, f"skip: {ok.sum()} matches")); continue
        A = fit_aff(sr[j[ok]], s[ok])                 # ref grid -> this night's grid
        print(night, "shift", dx, dy, "matches", int(ok.sum()))
        res = float(np.median(np.hypot(*(sr[j[ok]] @ A[:, :2].T + A[:, 2] - s[ok]).T)))
    X = A[0, 0] * xx + A[0, 1] * yy + A[0, 2]; Y = A[1, 0] * xx + A[1, 1] * yy + A[1, 2]
    warped = {k: ndi.map_coordinates(z[k + SUF], [Y, X], order=1, mode="nearest") for k in "RGB"}
    # transparency against 10-09: median star-flux ratio in apertures fixed on the 10-09 stack
    T = 1.0 if night == REF else float(np.median(ndi.sum(flat(sum(warped.values())), lab0, idx0) / f0))
    warped = {k: v / T for k, v in warped.items()}
    W.append((night, n, res, warped)); Ts.append(T)
# Noise per night from pairwise differences: real sky (faint stars, nebula) cancels, noise adds.
# var(i - j) = s_i^2 + s_j^2, solved by least squares over all pairs.
Ls = [sum(w[3].values()) for w in W]; m = len(W)
pairs = [(i, j) for i in range(m) for j in range(i + 1, m)]
M = np.zeros((len(pairs), m)); v = np.zeros(len(pairs))
for r, (i, j) in enumerate(pairs):
    M[r, i] = M[r, j] = 1; v[r] = noise(Ls[i] - Ls[j]) ** 2
s2 = np.clip(np.linalg.lstsq(M, v, rcond=None)[0], 1e-6, None)
wts = 1 / s2; iref = [w[0] for w in W].index(REF)
deep = {k: sum(wts[i] * W[i][3][k] for i in range(m)) / wts.sum() for k in "RGB"}
for i, (night, n, res, _) in enumerate(W):
    rows.append((night, n, f"T {Ts[i]:.2f}  res {res:.2f}  noise {s2[i] ** .5:.3f}  weight {wts[i] / wts[iref]:.2f}"))
for r in rows: print(*r)
Ld = sum(deep.values())
print(f"noise: 10-09 alone {s2[iref] ** .5:.3f}  deep {wts.sum() ** -.5:.3f}  gain {(wts.sum() / wts[iref]) ** .5:.2f}x  "
      f"(equal-weight frames would give {(sum(w[1] for w in W) / W[iref][1]) ** .5:.2f}x)")
np.save(sys.argv[1] + "-lum.npy", Ld); np.save(sys.argv[1] + "-ref.npy", Lr)
np.savez_compressed(sys.argv[1] + ".npz", **deep, rows=np.array(rows, dtype=object))

def show(ax, im, t):
    f = flat(im); s = noise(im)
    ax.imshow(np.arcsinh(np.clip(f / s, -3, None) / 3), cmap="gray", origin="upper",
              vmin=0, vmax=np.arcsinh(np.percentile(f / s, 99.8) / 3))
    ax.set_title(t, fontsize=10); ax.axis("off")
fig, ax = plt.subplots(1, 2, figsize=(10, 5.2), facecolor="black")
show(ax[0], Lr, f"10-09 alone ({int(ref['n'])} frames)")
nf = sum(w[1] for w in W)
show(ax[1], Ld, f"{len(W)} nights ({nf} frames)")
for a in ax: a.title.set_color("#E0E0E0")
plt.tight_layout(); plt.savefig(sys.argv[1] + ".png", dpi=110, facecolor="black")
