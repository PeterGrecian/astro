#!/usr/bin/env python3
"""hqfs night 2026-11-01: stars in Peter's probed frame 01491, clear stretch through the night,
field drift, a shift-and-add (derot) stack around 01491, and stars per night from the drift rate."""
import glob, os, sys
os.environ["OMP_NUM_THREADS"] = "2"
os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-11-01"
PROBE, PX, PY = 1491, 1220, 1020          # raw (Bayer) pixel from splay
OUT = os.path.expanduser("~/tmp/hqfs-count1101"); os.makedirs(OUT, exist_ok=True)
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{NIGHT}/*/*.fits.fz")}
idx = sorted(fs)
print("frames", len(idx), idx[0], idx[-1], flush=True)

def hdr(n):
    with fits.open(fs[n]) as h:
        return h[1].header

def load(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32)
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4, a

h = hdr(PROBE)
print({k: h[k] for k in ("EXPTIME", "GAIN", "DATE-OBS", "FOCUSPOS", "NAXIS1", "NAXIS2") if k in h})
h0, h1 = hdr(idx[0]), hdr(idx[-1])
print("first", h0.get("DATE-OBS"), "last", h1.get("DATE-OBS"))

def bgsub(im):
    bg = ndi.zoom(ndi.median_filter(im[::4, ::4], 15), 4, order=1)
    bg = np.pad(bg, ((0, max(0, im.shape[0] - bg.shape[0])), (0, max(0, im.shape[1] - bg.shape[1]))), mode="edge")
    return im - bg[:im.shape[0], :im.shape[1]]

def detect(d, k=6, amin=4, edge=20):
    s = ndi.gaussian_filter(d, 1.2)
    core = s[edge:-edge, edge:-edge]
    sig = 1.4826 * np.median(np.abs(core - np.median(core)))
    lab, n = ndi.label(s > k * sig)
    if n == 0:
        return [], sig
    area = ndi.sum(np.ones_like(s), lab, range(1, n + 1))
    flux = ndi.sum(d, lab, range(1, n + 1))
    com = ndi.center_of_mass(np.clip(d, 0, None), lab, range(1, n + 1))
    out = [(f, x, y, a) for f, (y, x), a in zip(flux, com, area)
           if a >= amin and edge < x < s.shape[1] - edge and edge < y < s.shape[0] - edge]
    return sorted(out, reverse=True), sig

# fixed pattern: median over the whole night (stars drift, hot pixels stay)
ref = np.median([load(n)[0] for n in idx[::max(len(idx) // 40, 1)]], axis=0)
np.save(f"{OUT}/ref.npy", ref)

# 1. the clear stretch
print("\n# survey: idx UTC sky_median noise nstars", flush=True)
step = max(len(idx) // 120, 1)
surv = []
for n in idx[::step]:
    im, _ = load(n)
    d = bgsub(im - ref)
    st, sig = detect(d)
    surv.append((n, len(st)))
    print(n, hdr(n).get("DATE-OBS", "")[11:19], f"{np.median(im):.0f} {sig:.2f}", len(st), flush=True)
np.save(f"{OUT}/survey.npy", np.array(surv))

# 2. the probed frame
im, raw = load(PROBE)
d = bgsub(im - ref)
st, sig = detect(d)
print(f"\n# frame {PROBE}: {len(st)} stars >6 sigma (noise {sig:.2f} ADU/superpixel)")
for k in (4, 5, 8, 12, 20):
    print(f"  >{k} sigma: {len(detect(d, k=k)[0])}")
sx, sy = PX // 2, PY // 2
c = raw[PY - 30:PY + 30, PX - 30:PX + 30]
print(f"probed star raw box max {c.max():.0f}, px>=4000: {(c >= 4000).sum()}")
near = sorted(st, key=lambda s: (s[1] - sx) ** 2 + (s[2] - sy) ** 2)[:1]
for f, x, y, a in near:
    rank = [s[0] for s in st].index(f) + 1
    print(f"probed star: superpixel ({x:.1f},{y:.1f}) flux {f:.0f} area {a:.0f} rank {rank} of {len(st)}")
    cut = np.clip(d[int(y) - 14:int(y) + 15, int(x) - 14:int(x) + 15], 0, None)
    ramp = " .:-=+*#%@"
    print("\n".join("".join(ramp[int(min(v / cut.max(), 1) * 9)] for v in r) for r in cut))
print("brightest 10: flux x y area")
for s_ in st[:10]:
    print(" ".join(f"{v:.0f}" for v in s_))

# 3. drift: phase correlation of star images k frames apart
def starimg(n):
    return np.clip(ndi.gaussian_filter(bgsub(load(n)[0] - ref), 1.0), 0, None)

def shift(a, b):
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-9)).real
    y, x = np.unravel_index(np.argmax(r), r.shape)
    if y > r.shape[0] // 2: y -= r.shape[0]
    if x > r.shape[1] // 2: x -= r.shape[1]
    return x, y, r.max()

A = starimg(PROBE)
print("\n# drift from frame", PROBE)
for k in (1, 2, 5, 10, 20):
    if PROBE + k in fs:
        dx, dy, q = shift(starimg(PROBE + k), A)
        print(f"  +{k} frames: dx {dx} dy {dy} superpixels (peak {q:.3f})")

# 4. shift-and-add stack, chaining shifts frame to frame
for N in (25, 75):
    ns = [n for n in range(PROBE - N, PROBE + N + 1) if n in fs]
    imgs = {n: bgsub(load(n)[0] - ref) for n in ns}
    acc, cnt = np.zeros_like(ref), np.zeros_like(ref)
    for n in ns:
        dx, dy, q = shift(np.clip(ndi.gaussian_filter(imgs[n], 1.0), 0, None), A)
        acc += ndi.shift(imgs[n], (-dy, -dx), order=0, mode="constant", cval=0)
        cnt += ndi.shift(np.ones_like(ref), (-dy, -dx), order=0, mode="constant", cval=0)
    stk = np.where(cnt > 0.8 * len(ns), acc / np.maximum(cnt, 1), 0)
    np.save(f"{OUT}/stack_{2*N+1}.npy", stk)
    sst, ssig = detect(stk)
    print(f"# stack of {len(ns)} frames: {len(sst)} stars >6 sigma (noise {ssig:.3f}, single {sig:.2f}, gain {sig/ssig:.1f}x)", flush=True)
