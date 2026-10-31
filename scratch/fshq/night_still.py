#!/usr/bin/env python3
"""fshq 2026-10-30, whole-night still: every frame, derotated about the pole, 2k colour, no deconvolution.
Known stars, found in the 1-in-10 still, are masked out of the background estimate."""
import glob, os, time
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"
os.nice(15)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from PIL import Image

N = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
OUT = os.path.expanduser("~/tmp/fshq-survey"); os.makedirs(OUT, exist_ok=True)
fs = {int(f.split("-")[-1].split(".")[0]): f for f in glob.glob(f"{N}/*/*.fits.fz")}
STEP = 1          # use 1 frame in STEP
BORDER = 100      # black px all round the finished still
NS = [n for n in sorted(fs)[::STEP] if n <= 14801]   # stop at the last frame of the 1-in-100 still: same canvas
T0 = sorted(fs)[len(fs) // 2]
W = np.radians(15.0411 * 3 / 3600)      # sidereal rotation per 3 s frame
OUT_W = 2000
start = time.time()

def channels(n):
    with fits.open(fs[n]) as h:
        a = h[1].data.astype(np.float32)
    return a[0::2, 0::2], (a[0::2, 1::2] + a[1::2, 0::2]) / 2, a[1::2, 1::2]

def bg(a, mask=None):
    """large-scale background from a 64 px clipped block mean, so haze and glow come out.
    Not a median: R and B are whole numbers, so a median snaps to a whole count and leaves
    a colour offset larger than the noise of the stack."""
    h, w = a.shape
    bh, bw = h // 64, w // 64
    b = a[:bh * 64, :bw * 64].reshape(bh, 64, bw, 64).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    med = np.median(b, axis=2, keepdims=True)
    keep = np.abs(b - med) < 6
    if mask is not None:
        keep &= ~mask[:bh * 64, :bw * 64].reshape(bh, 64, bw, 64).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    n = keep.sum(axis=2)
    m = (b * keep).sum(axis=2) / np.maximum(n, 1)
    thin = n < 400                    # a block mostly under a star takes its nearest well-sampled neighbour
    if thin.any() and not thin.all():
        iy, ix = ndi.distance_transform_edt(thin, return_distances=False, return_indices=True)
        m = m[iy, ix]
    return ndi.zoom(m, (h / bh, w / bw), order=1)

def level(cube):
    """clipped mean level of each frame in a cube, for the same reason"""
    med = np.median(cube, axis=(1, 2), keepdims=True)
    keep = np.abs(cube - med) < 6
    return ((cube * keep).sum(axis=(1, 2)) / keep.sum(axis=(1, 2)))[:, None, None]

# fixed pattern per channel, from every third frame
ref = []
for c in range(3):
    cube = np.array([channels(n)[c] for n in NS[::300 // STEP]])
    cube -= level(cube)
    ref.append(np.median(cube, axis=0))
    del cube
print(f"fixed pattern done {time.time() - start:.0f}s, using {len(NS)} frames", flush=True)

H, Wd = ref[0].shape
yy, xx = np.mgrid[:H, :Wd].astype(np.float32)

def sky(px, py, n, spin):
    """superpixel coordinates of frame n in the sky frame, with the pole at the origin"""
    th = W * (n - T0) + spin
    c, s = np.cos(th), np.sin(th)
    dx, dy = xx - px, yy - py
    return c * dx - s * dy, s * dx + c * dy

def residual(n, c, mask=None):
    a = channels(n)[c] - ref[c]
    return a - bg(a, mask)

px, py = -502, -1763      # from the pole search in the first run

# turn the sky so that the middle of the night's field sits straight above the pole: an arch, not a sideways C
fc = np.array([(Wd - 1) / 2 - px, (H - 1) / 2 - py])
spin = -np.pi / 2 - np.arctan2(fc[1], fc[0])
corners = []
for n in NS[::100 // STEP]:
    sx, sy = sky(px, py, n, spin)
    corners += [(sx[0, 0], sy[0, 0]), (sx[0, -1], sy[0, -1]), (sx[-1, 0], sy[-1, 0]), (sx[-1, -1], sy[-1, -1])]
corners = np.array(corners)
x0, y0 = corners.min(axis=0); x1, y1 = corners.max(axis=0)
scale = (x1 - x0 + 1) / OUT_W
OUT_H = int((y1 - y0 + 1) / scale) + 1
print(f"canvas {OUT_W} x {OUT_H}, {scale:.2f} superpixels per output px = {scale * 4.26:.1f} arcsec/px", flush=True)

prev = np.load(f"{OUT}/night_still_raw_v2.npy")
frames_prev = np.load(f"{OUT}/night_still_frames_v2.npy")
assert prev.shape[1:] == (OUT_H, OUT_W), (prev.shape, OUT_H, OUT_W)
pl = np.mean([p / (1.4826 * np.median(np.abs(p[frames_prev >= 60]))) for p in prev], axis=0)
psm = ndi.gaussian_filter(pl, 2)
star_mask = ndi.binary_dilation((psm > 3 * 1.4826 * np.median(np.abs(psm[frames_prev >= 60]))) & (frames_prev >= 60), iterations=8)
print("star mask covers", round(float(star_mask[frames_prev >= 60].mean()), 3), "of the arch", flush=True)
flat_mask = star_mask.ravel()

sums = np.zeros((3, OUT_H * OUT_W)); counts = np.zeros(OUT_H * OUT_W)
for k, n in enumerate(NS):
    sx, sy = sky(px, py, n, spin)
    i = ((sy - y0) / scale).astype(np.int64) * OUT_W + ((sx - x0) / scale).astype(np.int64)
    i = i.ravel()
    counts += np.bincount(i, minlength=counts.size)
    for c in range(3):
        sums[c] += np.bincount(i, residual(n, c, flat_mask[i].reshape(H, Wd)).ravel(), minlength=counts.size)
    if k % 1000 == 0:
        print(f"  frame {k + 1}/{len(NS)} {time.time() - start:.0f}s", flush=True)
    if k % 2000 == 1999:
        np.savez(f"{OUT}/night_still_checkpoint.npz", sums=sums.astype(np.float32), counts=counts.astype(np.float32), done=k + 1)
counts = counts.reshape(OUT_H, OUT_W)
img = np.array([s.reshape(OUT_H, OUT_W) / np.maximum(counts, 1) for s in sums])
frames_per_px = counts / scale ** 2
print("frames per output px where covered: median", round(float(np.median(frames_per_px[counts > 0])), 1), "max", round(float(frames_per_px.max()), 1), " covered fraction", round(float((counts > 0).mean()), 3))
good = frames_per_px >= 600 / STEP

np.save(f"{OUT}/night_still_raw_all.npy", img.astype(np.float32))
np.save(f"{OUT}/night_still_frames_all.npy", frames_per_px.astype(np.float32))

# stretch: remove any remaining level, scale each channel on its own noise, asinh
rgb = np.zeros_like(img)
for c in range(3):
    v = img[c][good]
    m = img[c] - v[np.abs(v - np.median(v)) < 1.5].mean()
    s = 1.4826 * np.median(np.abs(m[good]))
    rgb[c] = m / s
    print("RGB"[c], "noise per output px", round(float(s), 4), "top", round(float(np.percentile(m[good], 99.99)), 2))
lum = rgb.mean(axis=0)
fade = np.clip(frames_per_px * STEP / 1200, 0, 1) ** 0.7
ref_top = np.percentile(lum[good], 99.97)
out = np.arcsinh(np.clip(rgb + 0.5, 0, None) / 3) / np.arcsinh((ref_top + 0.5) / 3)
out = np.clip(out, 0, 1) * fade
final = np.pad((255 * out.transpose(1, 2, 0)).astype(np.uint8), ((BORDER, BORDER), (BORDER, BORDER), (0, 0)))
Image.fromarray(final).save(f"{OUT}/night_still_2k_all.png")
print("saved", final.shape, flush=True)

sm = ndi.gaussian_filter(lum, 2)
lab, nobj = ndi.label((sm > 4 * 1.4826 * np.median(np.abs(sm[good]))) & good)
sz = ndi.sum(np.ones_like(lab), lab, range(1, nobj + 1)) if nobj else np.array([])
print(f"blobs >4 sigma: {nobj}, of 30+ px: {(sz >= 30).sum()}, of 100+ px: {(sz >= 100).sum()}, biggest {sz.max() if nobj else 0:.0f}")
print(f"done {time.time() - start:.0f}s")

def halo(img3, label):
    """mean level against distance from the brightest stars, in counts: a dip is a shadow"""
    l = img3.mean(axis=0)
    labl, nn = ndi.label(psm > 12 * 1.4826 * np.median(np.abs(psm[frames_prev >= 60])))
    fl = ndi.sum(np.clip(l, 0, None), labl, range(1, nn + 1))
    top = np.argsort(-fl)[:8] + 1
    edge = 5
    prof = []
    for t in top:
        d = ndi.distance_transform_edt(labl != t)
        y, x = np.nonzero(labl == t)
        if y.min() < 90 or x.min() < 90 or y.max() > OUT_H - 90 or x.max() > OUT_W - 90:
            continue
        prof.append([l[(d > a) & (d <= a + 10) & (frames_prev >= 60)].mean() for a in range(0, 100, 10)])
    print(label, "distance 0-100 output px, every 10:", " ".join(f"{v:+.3f}" for v in np.mean(prof, axis=0)), f"({len(prof)} stars)")
halo(prev, "before")
halo(img, "after ")
disp = (255 * out.transpose(1, 2, 0))
cover = disp.sum(axis=2) > 0
for name, x0, x1 in (("left", 0, 400), ("left-mid", 400, 800), ("middle", 800, 1200), ("right-mid", 1200, 1600), ("right", 1600, 2000)):
    print(f"{name:10s} display mean RGB {disp[:, x0:x1][cover[:, x0:x1]].mean(axis=0).round(1)}")
for c in range(3):
    for name, x0, x1 in (("left", 0, 400), ("middle", 800, 1200), ("right", 1600, 2000)):
        print("RGB"[c], name, "raw clipped level", round(float(np.median(img[c][:, x0:x1][good[:, x0:x1]])), 3))

