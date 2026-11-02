#!/usr/bin/env python3
"""hqfs 2026-11-01 clear stretch: track stars frame to frame, fit a rigid motion (shift + rotation),
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

# stack in REF_N's frame
H, W = imgs[REF_N].shape
yy, xx = np.mgrid[:H, :W].astype(np.float32)
acc = np.zeros((H, W)); cnt = np.zeros((H, W))
for n in good:
    R, t = T[n]
    Ri = R.T; ti = -Ri @ t                        # REF coords -> frame-n coords
    sx = Ri[0, 0] * xx + Ri[0, 1] * yy + ti[0]; sy = Ri[1, 0] * xx + Ri[1, 1] * yy + ti[1]
    acc += ndi.map_coordinates(imgs[n], [sy, sx], order=1, cval=np.nan).astype(np.float64).__array__()
    inside = (sx >= 0) & (sx < W - 1) & (sy >= 0) & (sy < H - 1)
    cnt += inside
acc = np.nan_to_num(acc)
for frac in (0.9, 0.5):
    m = cnt >= frac * len(good)
    stk = np.where(m, acc / np.maximum(cnt, 1), 0)
    st, ssig = detect(stk)
    print(f"stack, pixels covered by >={int(frac*100)}% of {len(good)} frames ({m.mean()*100:.0f}% of field): {len(st)} stars >6 sigma, noise {ssig:.3f}")
    for k in (4, 10, 30):
        print(f"   >{k} sigma: {len(detect(stk, k=k)[0])}")
    np.save(f"{OUT}/derot_stack_{int(frac*100)}.npy", stk)
_, s1 = detect(imgs[REF_N])
print(f"single-frame noise {s1:.3f}; single frame stars {len(cats[REF_N])}")

# stars per night: new sky enters across the leading edge at the drift speed
area = H * W
sweep = v * (W * abs(vy) / v + H * abs(vx) / v) if v > 0 else 0   # superpx^2 of new sky per frame
per_frame_density = len(cats[REF_N]) / area
step = 12.0
print(f"new sky per frame {sweep:.0f} superpx^2 = {sweep/area*100:.2f}% of field; field crossing ~{(W if abs(vx)>abs(vy) else H)/v*step/60:.0f} min")
for hrs in (1.17, 6, 12):
    nfr = hrs * 3600 / step
    print(f"  {hrs:5.2f} h clear: ~{len(cats[REF_N]) + per_frame_density*sweep*nfr:.0f} distinct single-frame stars")
