#!/usr/bin/env python3
"""PSF (omega: defocus pupil + secondary + vanes) and deconvolution, hqfs 2026-11-01 clear stretch.
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
H, W = imgs[REF_N].shape
RC = 20                                   # cutout half-size, superpx
ramp = " .:-=+*#%@"
def ascii(c, step=1):
    c = np.clip(c, 0, None); c = c / c.max()
    return "\n".join("".join(ramp[int(v * 9)] for v in r) for r in c[::step])

# 1. empirical PSF in CAMERA coords: bright, isolated stars from every aligned frame, by 3x3 zone
cuts = {z: [] for z in range(9)}; allc = []
for n in good:
    cat = cats[n]
    if len(cat) < 3: continue
    tree = cKDTree(cat[:, :2])
    for x, y, f in cat[:12]:
        if not (RC + 2 < x < W - RC - 3 and RC + 2 < y < H - RC - 3): continue
        if len(tree.query_ball_point([x, y], 2.2 * RC)) > 1: continue
        ix, iy = int(round(x)), int(round(y))
        c = imgs[n][iy - RC - 2:iy + RC + 3, ix - RC - 2:ix + RC + 3]
        c = ndi.shift(c, (iy - y, ix - x), order=1)[2:-2, 2:-2]
        tot = c.sum()
        if tot <= 0: continue
        c = c / tot
        z = int(3 * y // H) * 3 + int(3 * x // W)
        cuts[z].append(c); allc.append(c)
psf = np.median(allc, axis=0); psf = np.clip(psf - np.median(psf[[0, -1], :]), 0, None); psf /= psf.sum()
np.save(f"{OUT}/psf_camera.npy", psf)
print(f"\n# empirical PSF from {len(allc)} star cutouts ({RC*2+1} superpx box), camera frame")
print(ascii(psf))
yy, xx = np.mgrid[-RC:RC + 1, -RC:RC + 1]; rr = np.hypot(xx, yy)
prof = [psf[(rr >= r) & (rr < r + 1)].mean() for r in range(RC)]
print("radial profile (x1e4):", " ".join(f"{1e4*p:.0f}" for p in prof))
print(f"encircled-energy 50% radius {np.interp(0.5, np.cumsum([psf[(rr>=r)&(rr<r+1)].sum() for r in range(RC)]), range(1, RC+1)):.1f} superpx")
print("zone: n  corr-with-mean  centroid-offset-of-light (superpx)")
for z in range(9):
    if len(cuts[z]) < 5: print(f"  {z}: {len(cuts[z])}"); continue
    p = np.median(cuts[z], axis=0); p = np.clip(p, 0, None); p /= p.sum()
    cc = np.corrcoef(p.ravel(), psf.ravel())[0, 1]
    np.save(f"{OUT}/psf_zone{z}.npy", p)
    print(f"  {z}: {len(cuts[z]):4d}  {cc:.3f}")
zmid = np.median(cuts[4], axis=0) if len(cuts[4]) >= 5 else psf
for z in (0, 2, 6, 8):
    if len(cuts[z]) >= 5:
        print(f"zone {z}:"); print(ascii(np.median(cuts[z], axis=0), 2))

# 2. matched filter on single frame REF_N vs the Gaussian detector
def mf_detect(d, kern, k=6, mask=None):
    s = fftconvolve(d, kern[::-1, ::-1], mode="same")
    core = s[30:-30, 30:-30] if mask is None else s[mask]
    sig = 1.4826 * np.median(np.abs(core - np.median(core)))
    lab, nn = ndi.label((s > k * sig) & (mask if mask is not None else True))
    return nn
d = imgs[REF_N]
for k in (5, 6, 8):
    g = len(detect(d, k=k)[0])
    print(f"frame {REF_N} >{k} sigma: gaussian {g}, omega matched filter {mf_detect(d, psf, k)}")

# 3. deconvolve each frame in camera coords (RL, few iterations), then derotate+stack as before
def rl(img, p, it):
    p = p / p.sum(); pf = p[::-1, ::-1]
    off = max(0, -img.min()) + 1.0                      # RL needs positive data: add sky back
    obs = img + off; est = np.full_like(obs, obs.mean())
    for _ in range(it):
        est *= fftconvolve(obs / np.maximum(fftconvolve(est, p, mode="same"), 1e-6), pf, mode="same")
    return est - off
yy2, xx2 = np.mgrid[:0, :0]
corn = np.array([[0, 0], [W, 0], [0, H], [W, H]], float)
allk = np.vstack([(T[n][0] @ corn.T).T + T[n][1] for n in good])
x0, y0 = np.floor(allk.min(0)).astype(int) - 2; x1, y1 = np.ceil(allk.max(0)).astype(int) + 2
CW, CH = x1 - x0, y1 - y0
gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
from PIL import Image
for IT in (0, 20):
    acc = np.zeros((CH, CW)); cnt = np.zeros((CH, CW))
    for n in good:
        im = imgs[n] if IT == 0 else rl(ndi.gaussian_filter(imgs[n], 0.7), psf, IT)
        R, t = T[n]; Ri = R.T; ti = -Ri @ t
        sx = Ri[0, 0] * gx + Ri[0, 1] * gy + ti[0]; sy = Ri[1, 0] * gx + Ri[1, 1] * gy + ti[1]
        inside = (sx >= 20) & (sx < W - 21) & (sy >= 20) & (sy < H - 21)
        acc += np.where(inside, ndi.map_coordinates(im, [sy, sx], order=1, cval=0), 0); cnt += inside
    mean = acc / np.maximum(cnt, 1); m = cnt >= 60
    np.save(f"{OUT}/mosaic_rl{IT}.npy", mean.astype(np.float32))
    # star count by matched filter on the deep part (>=60 frames); after RL use a small Gaussian kernel
    kern = psf if IT == 0 else np.exp(-(xx**2 + yy**2) / (2 * 1.2**2))
    nn = mf_detect(np.where(m, mean, 0), kern, 6, mask=m & (ndi.minimum_filter(cnt, 41) >= 60))
    print(f"mosaic RL{IT}: deep area {m.sum()/(W*H):.2f} fields, >6 sigma detections (matched) {nn}")
    v = np.clip(mean, 0, None); hi = np.percentile(v[m], 99.9)
    Image.fromarray((255 * np.clip(v / hi, 0, 1) ** 0.5).astype(np.uint8)).save(f"{OUT}/mosaic_rl{IT}.png")
    if IT:
        # a bright star before/after
        st, _ = detect(np.where(m, np.load(f"{OUT}/mosaic_rl0.npy"), 0))
        if len(st):
            x, y = int(st[0][0]), int(st[0][1])
            print("brightest star, raw stack:"); print(ascii(np.load(f"{OUT}/mosaic_rl0.npy")[y-RC:y+RC+1, x-RC:x+RC+1], 2))
            print("after RL20:"); print(ascii(mean[y-RC:y+RC+1, x-RC:x+RC+1], 2))
