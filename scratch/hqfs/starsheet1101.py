#!/usr/bin/env python3
"""Contact sheet + heatmaps of stars across brightness, each star averaged over its own frames in camera coords.
Based on derot1101c. Original docstring:
hqfs 2026-11-01 clear stretch: track stars frame to frame, fit a rigid motion (shift + rotation),
stack the stretch aligned on frame 01491, count stars, and turn the drift into stars per night."""
import glob, os
os.environ["OMP_NUM_THREADS"] = "2"
os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-11-01"
OUT = os.path.expanduser("~/tmp/hqfs-count1101")
REF_N, A, B = 1491, 1455, 1815
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{NIGHT}/*/*.fits.fz")}
ref = np.load(f"{OUT}/ref.npy")

def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32); t = h[1].header.get("DATE-OBS")
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4 - ref, t

def bgsub(im):
    bg = ndi.zoom(ndi.median_filter(im[::4, ::4], 15), 4, order=1)
    bg = np.pad(bg, ((0, max(0, im.shape[0] - bg.shape[0])), (0, max(0, im.shape[1] - bg.shape[1]))), mode="edge")
    return im - bg[:im.shape[0], :im.shape[1]]

def detect(d, k=6, amin=4, edge=20):
    s = ndi.gaussian_filter(d, 1.5)
    core = s[edge:-edge, edge:-edge]
    sig = 1.4826 * np.median(np.abs(core - np.median(core)))
    lab, n = ndi.label(s > k * sig)
    if n == 0:
        return np.zeros((0, 3)), sig
    area = ndi.sum(np.ones_like(s), lab, range(1, n + 1))
    flux = ndi.sum(d, lab, range(1, n + 1))
    com = np.array(ndi.center_of_mass(np.clip(d, 0, None), lab, range(1, n + 1)))
    ok = (area >= amin) & (com[:, 1] > edge) & (com[:, 1] < s.shape[1] - edge) & (com[:, 0] > edge) & (com[:, 0] < s.shape[0] - edge)
    o = np.c_[com[ok, 1], com[ok, 0], flux[ok]]
    return o[np.argsort(-o[:, 2])], sig

def rigid(p, q):
    """least-squares rotation+shift taking p -> q (N x 2)"""
    pc, qc = p.mean(0), q.mean(0)
    H = (p - pc).T @ (q - qc)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1; R = Vt.T @ U.T
    return R, qc - R @ pc

ns = [n for n in range(A, B + 1) if n in fs]
imgs, cats, times = {}, {}, {}
for n in ns:
    im, t = load(n)
    imgs[n] = bgsub(im); cats[n], _ = detect(imgs[n]); times[n] = t

# chain frame-to-frame from REF_N outward: transform T_n maps frame-n coords -> REF_N coords
T = {REF_N: (np.eye(2), np.zeros(2))}
def chain(order):
    prev = REF_N
    for n in order:
        R0, t0 = T[prev]
        p = cats[n][:40, :2]
        if len(p) < 4:
            continue
        guess = (R0 @ p.T).T + t0               # assume small motion since prev
        q = cats[REF_N][:60, :2]
        for it in range(3):
            d, j = cKDTree(q).query(guess, distance_upper_bound=8 if it else 15)
            m = np.isfinite(d)
            if m.sum() < 4:
                break
            R, t = rigid(p[m], q[j[m]])
            guess = (R @ p.T).T + t
        if m.sum() >= 4:
            T[n] = (R, t); prev = n
chain([n for n in ns if n > REF_N]); chain([n for n in ns if n < REF_N][::-1])
# a frame far from REF_N shares few stars with it, so the chain above matches against REF_N's catalogue
# only while overlap lasts: report how far it got
good0 = sorted(T)
# pole: fixed point c of each rigid T (R c + t = c)
cs = []
for n in good0:
    R, t = T[n]
    if abs(n - REF_N) >= 8:
        cs.append(np.linalg.solve(np.eye(2) - R, t))
pole = np.median(cs, axis=0)
om = np.median([np.arctan2(T[n][0][1, 0], T[n][0][0, 0]) / (n - REF_N) for n in good0 if n != REF_N])
print(f"pole (superpx, frame {REF_N} coords) ({pole[0]:.0f},{pole[1]:.0f}) scatter {np.std(cs, axis=0).round(0)}; omega {np.degrees(om)*1000:.2f} mdeg/frame (sidereal 50.14)")
qtree = None
T = {}
for n in ns:
    th = om * (n - REF_N)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]); t = pole - R @ pole
    p = cats[n][:40, :2]
    q = cats[REF_N][:80, :2]
    if len(p) >= 3:
        d, j = cKDTree(q).query((R @ p.T).T + t, distance_upper_bound=6)
        m = np.isfinite(d)
        if m.sum() >= 3:
            off = np.median(q[j[m]] - ((R @ p[m].T).T + t), axis=0)
            t = t + off
        nm = int(m.sum())
    else:
        nm = 0
    if len(cats[n]) >= 8:
        T[n] = (R, t)
    if (n - A) % 30 == 0:
        print(f"  model {n}: {len(cats[n])} stars, {nm} matched to {REF_N}")
good = sorted(T)
print(f"aligned {len(good)} of {len(ns)} frames, {good[0]}..{good[-1]}")
for n in good[::25]:
    R, t = T[n]
    ang = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    print(f"  {n} {times[n][11:19]}  shift ({t[0]:+.1f},{t[1]:+.1f}) superpx  rot {ang:+.3f} deg  stars {len(cats[n])}")

# drift rate: linear fit of the frame-centre position in REF coords vs frame number
cen = np.array([imgs[REF_N].shape[1] / 2, imgs[REF_N].shape[0] / 2])
xs = np.array([n for n in good]); ys = np.array([T[n][0] @ cen + T[n][1] for n in good])
vx, vy = np.polyfit(xs, ys[:, 0], 1)[0], np.polyfit(xs, ys[:, 1], 1)[0]
rot = np.polyfit(xs, [np.degrees(np.arctan2(T[n][0][1, 0], T[n][0][0, 0])) for n in good], 1)[0]
v = np.hypot(vx, vy)
print(f"drift {v:.3f} superpx/frame ({vx:+.3f},{vy:+.3f}), rotation {rot*1000:+.3f} mdeg/frame")


import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
H, W = imgs[REF_N].shape; RC = 20
mean = np.load(f"{OUT}/mosaic_mean.npy"); cntm = np.load(f"{OUT}/mosaic_cnt.npy")
corn = np.array([[0, 0], [W, 0], [0, H], [W, H]], float)
allk = np.vstack([(T[n][0] @ corn.T).T + T[n][1] for n in good])
x0, y0 = np.floor(allk.min(0)).astype(int) - 2, None
x0, y0 = np.floor(allk.min(0)).astype(int) - 2
st, _ = detect(np.where(cntm >= 40, mean, 0), k=6)
st = st[[cKDTree(st[:, :2]).query(p, 2)[0][1] > 30 for p in st[:, :2]]]      # isolated
pick = np.unique(np.round(np.linspace(0, len(st) - 1, 24)).astype(int))
tiles = []
for i in pick:
    X, Y, F = st[i]; Pref = np.array([X + x0, Y + y0])
    acc = np.zeros((2 * RC + 1, 2 * RC + 1)); k = 0
    for n in good:
        R, t = T[n]; Ri = R.T; x, y = Ri @ Pref + (-Ri @ t)
        if not (RC + 2 < x < W - RC - 3 and RC + 2 < y < H - RC - 3): continue
        ix, iy = int(round(x)), int(round(y))
        c = imgs[n][iy - RC - 2:iy + RC + 3, ix - RC - 2:ix + RC + 3]
        acc += ndi.shift(c, (iy - y, ix - x), order=1)[2:-2, 2:-2]; k += 1
    if k < 10: continue
    c = acc / k
    edge = np.r_[c[:3].ravel(), c[-3:].ravel(), c[:, :3].ravel(), c[:, -3:].ravel()]
    c = c - np.median(edge); noise = 1.4826 * np.median(np.abs(edge - np.median(edge)))
    tiles.append((F, k, c, c.max() / noise, (x, y)))
print(f"{len(tiles)} tiles from {len(st)} isolated stars")
cmap = LinearSegmentedColormap.from_list("blue_on_black", ["#000000", "#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb"])
L = 60 / 2.132                                     # 1 arcmin in superpx (theoretical scale)
for kind in ("grey", "heat"):
    fig, axs = plt.subplots(4, 6, figsize=(15, 11), facecolor="#000000")
    for ax, (F, k, c, snr, (cx, cy)) in zip(axs.flat, tiles):
        ax.set_facecolor("#000000"); ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values(): sp.set_color("#2C2C2E")
        if kind == "grey":
            sig = max(np.percentile(np.abs(c), 50) * 1.4826, 1e-6)
            v = np.arcsinh(np.clip(c, 0, None) / sig) / np.arcsinh(c.max() / sig)
            im = ax.imshow(v, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
        else:
            im = ax.imshow(np.clip(c / c.max(), 0, 1), cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(f"flux {F:.0f}  S/N {snr:.0f}\n{k} frames, cam ({2*cx:.0f},{2*cy:.0f})", color="#E0E0E0", fontsize=8)
    for ax in list(axs.flat)[len(tiles):]: ax.axis("off")
    a0 = axs.flat[0]
    a0.plot([3, 3 + L], [2 * RC - 3] * 2, color="#E0E0E0", lw=2); a0.text(3, 2 * RC - 5, "1 arcmin*", color="#E0E0E0", fontsize=7)
    what = ("asinh stretch, each tile to its own peak" if kind == "grey"
            else "linear, fraction of each tile's own peak (0 black -> 1 pale blue)")
    fig.suptitle(f"hqfs 2026-11-01 22:28-23:38 UTC: stars brightest -> faintest, each averaged over its own 12 s frames in camera coords ({what})",
                 color="#E0E0E0", fontsize=10)
    fig.text(0.01, 0.005, f"tiles {2*RC+1} superpx = {(2*RC+1)*2.132/60:.1f} arcmin square, all at one scale. *theoretical plate scale 1.066\"/px, unmeasured. "
             "flux = ADU summed over the star in the derotated stack; cam = raw-pixel position in frame 1491's camera frame.", color="#8E8E93", fontsize=8)
    if kind == "heat":
        cb = fig.colorbar(im, ax=axs, fraction=0.015, pad=0.01); cb.set_label("fraction of tile peak", color="#E0E0E0")
        cb.ax.yaxis.set_tick_params(color="#8E8E93"); plt.setp(cb.ax.get_yticklabels(), color="#8E8E93")
    fig.savefig(f"{OUT}/hqfs-1101-stars-{kind}.png", dpi=110, facecolor="#000000")
    print("saved", kind)
