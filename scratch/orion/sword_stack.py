"""Stack the Orion sword (M42) from one eclipticam night, keeping R/G/B.

Runs on muppet via bigstore-run. eclipticam does not track, so the sword
drifts ~11 px/frame and the field turns slowly. Starting at a reference frame,
stars in a box around the sword are matched frame to frame (forward and back),
a similarity transform (shift + rotation + scale) is fitted per frame, and each
Bayer colour plane (R, G=(G1+G2)/2, B at superpixel resolution) is resampled
onto the reference grid. Sky is subtracted per plane per frame; the stack is a
sigma-clipped mean so satellite and aircraft trails drop out.

    bigstore-run sword_stack.py NIGHT REF_EPOCH_MS CX CY [--half 120]
"""
import argparse, glob, os, sys
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

BASE = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data")
ap = argparse.ArgumentParser()
ap.add_argument("night"); ap.add_argument("ref", type=int)
ap.add_argument("cx", type=float); ap.add_argument("cy", type=float)
ap.add_argument("--half", type=int, default=120, help="output half-size, superpixels")
ap.add_argument("--track", type=int, default=200, help="star-match half-box, superpixels")
ap.add_argument("--ymax", type=float, default=1900, help="stop when sword below this full-res row")
ap.add_argument("--utc-max", default="04:30")
ap.add_argument("--res-max", type=float, default=1.2, help="use frame only if median fit residual (superpixels) below")
ap.add_argument("--sky-max", type=float, default=80.0, help="skip frames with header MEAN above")
a = ap.parse_args()

night_dir = f"{BASE}/eclipticam-frames/night/{a.night}/v3w"
files = sorted(glob.glob(f"{night_dir}/*/*.fits.fz"), key=lambda p: int(os.path.basename(p).split(".")[0]))
eps = [int(os.path.basename(p).split(".")[0]) for p in files]
iref = eps.index(a.ref)


def planes(path):
    h = fits.open(path)[1]
    d = h.data.astype(np.float32) - h.header.get("BLACKLVL", 64)
    return {"R": d[0::2, 0::2], "G": 0.5 * (d[0::2, 1::2] + d[1::2, 0::2]), "B": d[1::2, 1::2]}, h.header


def stars(lum, cx, cy, half):
    """Star centroids (superpixel coords) in a box around (cx, cy)."""
    x0, y0 = int(max(cx - half, 0)), int(max(cy - half, 0))
    sub = lum[y0:int(cy + half), x0:int(cx + half)]
    sub = sub - ndi.median_filter(sub, size=31)
    sm = ndi.gaussian_filter(sub, 1.5)
    noise = 1.4826 * np.median(np.abs(sm - np.median(sm)))
    lab, n = ndi.label(sm > 8 * noise)
    if n == 0:
        return np.zeros((0, 3))
    idx = np.arange(1, n + 1)
    com = ndi.center_of_mass(np.clip(sub, 0, None), lab, idx)
    flux = ndi.sum(sub, lab, idx)
    out = np.array([(c[1] + x0, c[0] + y0, f) for c, f in zip(com, flux)])
    return out[np.argsort(-out[:, 2])][:40]


def fit_aff(src, dst):
    """dst = A @ [x, y, 1]: 6-parameter affine, absorbs the lens's local stretch."""
    X = np.column_stack([src, np.ones(len(src))])
    A, *_ = np.linalg.lstsq(X, dst, rcond=None)
    return A.T                                   # 2x3


def apply(A, xy):
    xy = np.atleast_2d(xy)
    return xy @ A[:, :2].T + A[:, 2]


def rot_deg(A):
    return float(np.degrees(np.arctan2(A[1, 0] - A[0, 1], A[0, 0] + A[1, 1])))


def xshift(prev, cur, cx, cy, h=150):
    """Shift (dx, dy) of cur relative to prev in a box at (cx, cy), by FFT cross-correlation."""
    cx, cy = int(cx), int(cy)
    def patch(l):
        q = l[cy - h:cy + h, cx - h:cx + h]
        q = q - ndi.median_filter(q, size=31)
        return np.clip(q, 0, np.percentile(q, 99.9))
    A, B = patch(prev), patch(cur)
    c = np.real(np.fft.ifft2(np.conj(np.fft.fft2(A)) * np.fft.fft2(B)))
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    return (dx - 2 * h if dx > h else dx), (dy - 2 * h if dy > h else dy)


def match(ref_xy, cur_xy, A, tol):
    pred = apply(A, ref_xy)
    pairs = []
    for i, p in enumerate(pred):
        d = np.hypot(*(cur_xy - p).T); j = int(np.argmin(d))
        if d[j] < tol:
            pairs.append((i, j))
    return pairs


# reference
cx, cy = a.cx / 2, a.cy / 2
P0, H0 = planes(files[iref])
lum0 = P0["R"] + P0["G"] + P0["B"]
ref_st = stars(lum0, cx, cy, a.track)
print(f"ref {a.ref}  {len(ref_st)} stars in track box", flush=True)

yy, xx = np.mgrid[-a.half:a.half, -a.half:a.half].astype(np.float32)
grid = np.column_stack([(xx + cx).ravel(), (yy + cy).ravel()])   # reference superpixel coords
samples = {"R": [], "G": [], "B": []}
log = []


def sample(P, A):
    z = apply(A, grid)
    X, Y = (int(v) for v in apply(A, [cx, cy])[0])
    out = {}
    for k in "RGB":
        pl = P[k]
        v = ndi.map_coordinates(pl, [z[:, 1], z[:, 0]], order=1, mode="nearest").reshape(xx.shape)
        box = pl[max(Y - 250, 0):Y + 250, max(X - 250, 0):X + 250]   # local sky
        out[k] = v - np.median(box)
    return out


I = np.array([[1.0, 0, 0], [0, 1.0, 0]])
for direction in (+1, -1):
    A = I.copy(); prev_lum = lum0
    i = iref if direction == 1 else iref - 1
    misses = 0
    while 0 <= i < len(files):
        P, H = planes(files[i])
        utc = H["DATE-OBS"][11:16]
        if direction == 1 and utc > a.utc_max:
            break
        lum = P["R"] + P["G"] + P["B"]
        pc = apply(A, [cx, cy])[0]
        if not (a.track < pc[0] < lum.shape[1] - a.track and a.track < pc[1] < lum.shape[0] - a.track):
            print(f"  {utc} sword box leaves the frame, stop", flush=True); break
        dx, dy = xshift(prev_lum, lum, pc[0], pc[1])   # drift since the last frame (~6 superpixels)
        Ap = A.copy(); Ap[:, 2] += (dx, dy)
        pc = apply(Ap, [cx, cy])[0]
        cur = stars(lum, pc[0], pc[1], a.track)
        pairs = match(ref_st[:, :2], cur[:, :2], Ap, tol=4) if len(cur) else []
        if len(pairs) >= 8:
            src = ref_st[[p[0] for p in pairs], :2]; dst = cur[[p[1] for p in pairs], :2]
            A2 = fit_aff(src, dst)
            res = np.hypot(*(apply(A2, src) - dst).T)
            keep = res < max(3 * np.median(res), 1.0)
            if keep.sum() >= 8:
                A2 = fit_aff(src[keep], dst[keep])
                res = np.hypot(*(apply(A2, src[keep]) - dst[keep]).T)
            pc = apply(A2, [cx, cy])[0]
            if 2 * pc[1] > a.ymax:
                print(f"  {utc} sword at y {2*pc[1]:.0f}: below limit, stop", flush=True); break
            used = bool(H.get("MEAN", 0) <= a.sky_max and np.median(res) <= a.res_max)
            if used:
                smp = sample(P, A2)
                for k in "RGB":
                    samples[k].append(smp[k])
            log.append((eps[i], utc, len(pairs), float(np.median(res)), rot_deg(A2), used))
            print(f"  {utc} n={len(pairs):2d} res={np.median(res):.2f} rot={rot_deg(A2):+.2f} used={used}", flush=True)
            A = A2; misses = 0
        else:
            misses += 1
            print(f"  {utc} only {len(pairs)} matches (miss {misses})", flush=True)
            if misses >= 5:
                break
            A = Ap
        prev_lum = lum
        i += direction

n = len(samples["G"])
print(f"stacking {n} frames", flush=True)
out = {}
for k in "RGB":
    cube = np.stack(samples[k])
    med = np.median(cube, 0); mad = 1.4826 * np.median(np.abs(cube - med), 0) + 1e-3
    w = np.abs(cube - med) < 3 * mad
    out[k] = (cube * w).sum(0) / np.maximum(w.sum(0), 1)
    out[k + "_med"] = med
dest = f"{BASE}/eclipticam-frames/night/{a.night}/sword-stack.npz"
np.savez_compressed(dest, **out, n=n, cx=a.cx, cy=a.cy, ref=a.ref,
                    log=np.array(log, dtype=object))
print("wrote", dest)
