"""Richardson-Lucy trail deconvolution of the 9-night deep sword stack, against 10-09 alone."""
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.signal import fftconvolve
cx, cy = 508, 526

def prep(z):
    L = (z["R"] + 2 * z["G"] + z["B"]).astype(float); h = L.shape[0] // 2
    yy, xx = np.mgrid[-h:h, -h:h]; m = (np.hypot(xx, yy) > 50) & (np.abs(xx) < h - 14) & (np.abs(yy) < h - 14)
    for _ in range(4):
        A = np.column_stack([np.ones(m.sum()), xx[m], yy[m]]); c, *_ = np.linalg.lstsq(A, L[m], rcond=None)
        Lb = L - (c[0] + c[1] * xx + c[2] * yy); s = 1.4826 * np.median(np.abs(Lb[m])); m &= np.abs(Lb) < 2.5 * s
    return Lb, h

def line_kernel(length=6.0, ang=9.3, n=17, sub=20):
    k = np.zeros((n, n)); t = np.linspace(-length / 2, length / 2, int(length * sub))
    a = np.radians(ang); xs = n // 2 + t * np.cos(a); ys = n // 2 + t * np.sin(a)
    for x, y in zip(xs, ys):
        x0, y0 = int(np.floor(x)), int(np.floor(y)); fx, fy = x - x0, y - y0
        k[y0, x0] += (1 - fx) * (1 - fy); k[y0, x0 + 1] += fx * (1 - fy); k[y0 + 1, x0] += (1 - fx) * fy; k[y0 + 1, x0 + 1] += fx * fy
    return k / k.sum()
K = line_kernel(); Kf = K[::-1, ::-1]

def rl(Lb, s, n):
    off = 20 * s; obs = np.clip(Lb + off, 1e-3, None); est = np.full_like(obs, obs.mean())
    for _ in range(n):
        est *= fftconvolve(obs / np.maximum(fftconvolve(est, K, mode="same"), 1e-6), Kf, mode="same")
    return est - off

def shape(img, X, Y, h, r=8):
    x, y = X // 2 - cx + h, Y // 2 - cy + h; c = np.clip(img[y - r:y + r + 1, x - r:x + r + 1], 0, None)
    c = np.where(c < 0.15 * c.max(), 0, c); q, p = np.mgrid[-r:r + 1, -r:r + 1]; w = c.sum()
    mx, my = (c * p).sum() / w, (c * q).sum() / w
    I = np.array([[(c * (p - mx) ** 2).sum(), (c * (p - mx) * (q - my)).sum()], [(c * (p - mx) * (q - my)).sum(), (c * (q - my) ** 2).sum()]]) / w
    ev = np.linalg.eigvalsh(I); return np.sqrt(ev[1]), np.sqrt(ev[0])

STARS = [(1027, 904), (959, 924), (1076, 875), (986, 1016)]
R = "/mnt/muppet/bigstore/eclipticam-frames/night"
out = {}
for name, path in [("10-09", f"{R}/2026-10-09/sword-stack-w.npz"), ("deep", "weighted.npz")]:
    Lb, h = prep(np.load(path, allow_pickle=True))
    s = 1.4826 * np.median(np.abs(Lb[20:-20, 20:-20] - np.median(Lb[20:-20, 20:-20])))
    res = {0: Lb}
    for n in (30, 60, 100): res[n] = rl(Lb, s, n)
    out[name] = (res, s, h)
    for n, img in res.items():
        sh = [shape(img, X, Y, h) for X, Y in STARS]
        print(f"{name:5s} RL {n:3d}: belt " + "  ".join(f"{a / b:.2f}:1" for a, b in sh[:3]) +
              f"  HD37410 {sh[3][0] / sh[3][1]:.2f}:1   belt FWHM-eq short axis {np.mean([2 * 2.355 * b for a, b in sh[:3]]):.1f} px")
    np.save(f"rl-{name}.npy", np.array([res[k] for k in (0, 30, 60, 100)]))
