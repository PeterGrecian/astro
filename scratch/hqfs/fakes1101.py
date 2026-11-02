#!/usr/bin/env python3
"""Fake-star test of three detectors (gaussian, omega matched filter, per-frame RL) on the derotated hqfs mosaic.
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


from scipy.signal import fftconvolve
rng = np.random.default_rng(1)
H, W = imgs[REF_N].shape
RC = 20
zpsf = [np.load(f"{OUT}/psf_zone{z}.npy") for z in range(9)]
zpsf = [np.clip(p, 0, None) / np.clip(p, 0, None).sum() for p in zpsf]
psf = np.load(f"{OUT}/psf_camera.npy")
yy, xx = np.mgrid[-RC:RC + 1, -RC:RC + 1]
gk = np.exp(-(xx**2 + yy**2) / (2 * 1.2**2))

corn = np.array([[0, 0], [W, 0], [0, H], [W, H]], float)
allk = np.vstack([(T[n][0] @ corn.T).T + T[n][1] for n in good])
x0, y0 = np.floor(allk.min(0)).astype(int) - 2; x1, y1 = np.ceil(allk.max(0)).astype(int) + 2
CW, CH = x1 - x0, y1 - y0
gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
maps = {}
for n in good:
    R, t = T[n]; Ri = R.T; ti = -Ri @ t
    sx = Ri[0, 0] * gx + Ri[0, 1] * gy + ti[0]; sy = Ri[1, 0] * gx + Ri[1, 1] * gy + ti[1]
    maps[n] = (sx, sy, (sx >= 20) & (sx < W - 21) & (sy >= 20) & (sy < H - 21))
cnt = sum(maps[n][2].astype(np.int32) for n in good)
deep = ndi.minimum_filter(cnt, 41) >= 60
print(f"canvas {CW}x{CH}; deep area {deep.sum()/(W*H):.2f} fields", flush=True)

# real stars on the canvas (from the plain stack) so fakes avoid them
def stackit(frames_ns, fn):
    acc = np.zeros((CH, CW)); c = np.zeros((CH, CW))
    for n in frames_ns:
        sx, sy, ins = maps[n]
        acc += np.where(ins, ndi.map_coordinates(fn(n), [sy, sx], order=1, cval=0), 0); c += ins
    return acc / np.maximum(c, 1)
plain = stackit(good, lambda n: imgs[n])
real, _ = detect(np.where(deep, plain, 0), k=4)
rtree = cKDTree(real[:, :2]) if len(real) else None

# fakes on a jittered grid in the deep area, sky coords = canvas coords + (x0,y0) -> REF coords
cand = []
for cy in range(30, CH - 30, 34):
    for cx in range(30, CW - 30, 34):
        px, py = cx + rng.uniform(-6, 6), cy + rng.uniform(-6, 6)
        if deep[int(py), int(px)] and (rtree is None or rtree.query([px, py])[0] > 25):
            cand.append((px, py))
cand = np.array(cand)
fl = np.exp(rng.uniform(np.log(15), np.log(1500), len(cand)))
print(f"{len(cand)} fakes, flux 15-1500 (real stars: brightest {real[0,2]:.0f}, 6-sigma single-frame ~ see below)", flush=True)
fref = cand + [x0, y0]                       # REF_N coords

def with_fakes(n):
    im = imgs[n].copy()
    R, t = T[n]; Ri = R.T; ti = -Ri @ t
    for (X, Y), f in zip(fref, fl):
        x, y = Ri @ np.array([X, Y]) + ti
        if not (RC + 1 < x < W - RC - 2 and RC + 1 < y < H - RC - 2): continue
        z = int(3 * y // H) * 3 + int(3 * x // W)
        ix, iy = int(np.floor(x)), int(np.floor(y))
        p = ndi.shift(zpsf[z], (y - iy, x - ix), order=1)
        im[iy - RC:iy + RC + 1, ix - RC:ix + RC + 1] += f * p
    return im

def rl(img, p, it=20):
    pf = p[::-1, ::-1]; off = max(0, -img.min()) + 1.0
    obs = img + off; est = np.full_like(obs, obs.mean())
    for _ in range(it):
        est *= fftconvolve(obs / np.maximum(fftconvolve(est, p, mode="same"), 1e-6), pf, mode="same")
    return est - off

# rotation-averaged PSF for the matched filter on the stack (sky frame)
angs = [np.arctan2(T[n][0][1, 0], T[n][0][0, 0]) for n in good]
rpsf = np.mean([ndi.rotate(psf, np.degrees(a), reshape=False, order=1) for a in angs[::10]], axis=0); rpsf /= rpsf.sum()

def find(img, kern, k):
    s = fftconvolve(np.where(deep, img, 0), kern[::-1, ::-1], mode="same")
    sig = 1.4826 * np.median(np.abs(s[deep] - np.median(s[deep])))
    lab, nn = ndi.label((s > k * sig) & deep)
    if not nn: return np.zeros((0, 2))
    return np.array(ndi.maximum_position(s, lab, range(1, nn + 1)))[:, ::-1].astype(float)

def score(name, img, kern):
    for k in (5, 6, 8):
        pos = find(img, kern, k)
        hit = np.zeros(len(cand), bool)
        if len(pos):
            d, _ = cKDTree(pos).query(cand); hit = d < 4
        bins = [15, 30, 60, 120, 250, 500, 1500]
        rec = [hit[(fl >= a) & (fl < b)].mean() for a, b in zip(bins, bins[1:])]
        print(f"  {name:8s} >{k}sig: {len(pos):4d} detections; recovered by flux " +
              " ".join(f"{a}-{b}:{r*100:3.0f}%" for a, b, r in zip(bins, bins[1:], rec)), flush=True)

print("\n# with fakes (all frames)")
fk = stackit(good, with_fakes)
score("gauss", fk, gk); score("omega", fk, rpsf)
cache = {}
def rlfake(n):
    return rl(ndi.gaussian_filter(with_fakes(n), 0.7), psf)
rlk = stackit(good, rlfake)
score("RL20", rlk, gk)
np.save(f"{OUT}/fake_plain.npy", fk.astype(np.float32)); np.save(f"{OUT}/fake_rl.npy", rlk.astype(np.float32))
np.save(f"{OUT}/fake_list.npy", np.c_[cand, fl])

print("\n# false detections: odd vs even half-stacks, NO fakes. Unmatched = in one half, not within 4 px in the other (at k-1 sigma)")
odd, even = good[0::2], good[1::2]
for name, fn, kern in (("gauss", lambda n: imgs[n], gk), ("omega", lambda n: imgs[n], rpsf),
                       ("RL20", lambda n: rl(ndi.gaussian_filter(imgs[n], 0.7), psf), gk)):
    A_, B_ = stackit(odd, fn), stackit(even, fn)
    for k in (5, 6, 8):
        pa, pb = find(A_, kern, k), find(B_, kern, k - 1)
        un = (cKDTree(pb).query(pa)[0] > 4).sum() if len(pa) and len(pb) else len(pa)
        print(f"  {name:6s} >{k}sig: odd {len(pa):4d}, unmatched in even {un:4d} ({un/max(len(pa),1)*100:.0f}%)", flush=True)
