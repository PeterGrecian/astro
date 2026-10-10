"""Stack the Orion sword (M42) from one eclipticam night, keeping R/G/B.

Runs on muppet via bigstore-run. eclipticam does not track, so the sword
drifts ~11 px/frame and the field turns slowly. Starting at a reference frame,
stars in a box around the sword are matched frame to frame (forward and back),
a similarity transform (shift + rotation + scale) is fitted per frame, and each
Bayer colour plane (R, G=(G1+G2)/2, B at superpixel resolution) is resampled
onto the reference grid. Sky is subtracted per plane per frame.

Frames are weighted, not just kept or dropped. Each frame's transparency t is
the median flux ratio of the reference stars against the reference frame, and
its noise sigma is the robust scatter of its sky. A frame is scaled by 1/t
(to reference-frame brightness) and weighted t^2/sigma^2, so a hazy or twilight
frame counts for little instead of diluting the good ones. Pixels more than
3 sigma (that frame's own sigma) from the median are clipped, which removes
satellite and aircraft trails. The equal-weight mean is kept alongside for
comparison. The night ends when the sun climbs above --sun-max degrees.

    bigstore-run sword-stack-draft.py NIGHT REF_EPOCH_MS CX CY [--out PATH] (REF may be predicted: nearest frame)
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
ap.add_argument("--sun-max", type=float, default=-12.0, help="stop when the sun is above this altitude (deg)")
ap.add_argument("--t-min", type=float, default=0.3, help="skip frames with transparency below")
ap.add_argument("--res-max", type=float, default=1.2, help="use frame only if median fit residual (superpixels) below")
ap.add_argument("--out", help="output .npz (default: the night's sword-stack.npz)")
ap.add_argument("--sky-max", type=float, default=150.0, help="skip frames with header MEAN above")
a = ap.parse_args()

night_dir = f"{BASE}/eclipticam-frames/night/{a.night}/v3w"
files = sorted(glob.glob(f"{night_dir}/*/*.fits.fz"), key=lambda p: int(os.path.basename(p).split(".")[0]))
eps = [int(os.path.basename(p).split(".")[0]) for p in files]
iref = int(np.argmin(np.abs(np.array(eps) - a.ref)))   # nearest frame; ref may be predicted
a.ref = eps[iref]


def sun_alt(epoch_ms, lat=51.3948, lon=-0.2923):
    """Solar altitude in degrees (NOAA low-precision formulae, ~0.1 deg)."""
    d = epoch_ms / 86400000.0 + 2440587.5 - 2451545.0
    g = np.radians(357.529 + 0.98560028 * d); q = 280.459 + 0.98564736 * d
    L = np.radians(q + 1.915 * np.sin(g) + 0.020 * np.sin(2 * g))
    e = np.radians(23.439 - 0.00000036 * d)
    ra = np.arctan2(np.cos(e) * np.sin(L), np.cos(L)); dec = np.arcsin(np.sin(e) * np.sin(L))
    gmst = np.radians((18.697374558 + 24.06570982441908 * d) % 24 * 15)
    ha = gmst + np.radians(lon) - ra; la = np.radians(lat)
    return float(np.degrees(np.arcsin(np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(ha))))


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
frames = []      # (epoch, utc, t, sigma, res, sun) per used frame
log = []
As = {}          # epoch -> affine (ref superpixels -> frame superpixels), for per-frame kernels


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


def flux_ratio(L, L0, lab0, n0):
    """Transparency: median over reference stars of flux(this frame)/flux(reference frame)."""
    idx = np.arange(1, n0 + 1)
    f0 = ndi.sum(L0, lab0, idx); f = ndi.sum(L, lab0, idx)
    ok = f0 > 0
    return float(np.median(f[ok] / f0[ok]))


def sky_sigma(L):
    f = L - ndi.median_filter(L, size=25)
    return float(1.4826 * np.median(np.abs(f - np.median(f))))


I = np.array([[1.0, 0, 0], [0, 1.0, 0]])
Lref = None
for direction in (+1, -1):
    A = I.copy(); prev_lum = lum0
    i = iref if direction == 1 else iref - 1
    misses = 0
    while 0 <= i < len(files):
        P, H = planes(files[i])
        utc = H["DATE-OBS"][11:16]
        sun = sun_alt(eps[i])
        if sun > a.sun_max:
            if direction == 1:
                print(f"  {utc} sun at {sun:.1f} deg, stop", flush=True); break
            # going back the sky darkens: keep tracking through twilight, but do not stack it
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
            used = bool(H.get("MEAN", 0) <= a.sky_max and np.median(res) <= a.res_max and sun <= a.sun_max)
            if used:
                smp = sample(P, A2)
                Ls = smp["R"] + smp["G"] + smp["B"]
                if Lref is None:            # the reference frame comes first: fix the star apertures on it
                    sg = sky_sigma(Ls)
                    lab0, n0 = ndi.label(ndi.binary_dilation(ndi.gaussian_filter(Ls, 1.5) > 5 * sg, iterations=3))
                    Lref = Ls
                t = flux_ratio(Ls, Lref, lab0, n0); sg = sky_sigma(Ls)
                used = t >= a.t_min
                if used:
                    for k in "RGB":
                        samples[k].append(smp[k] / t)
                    frames.append((eps[i], utc, t, sg, float(np.median(res)), sun))
            As[eps[i]] = A2.copy()
            log.append((eps[i], utc, len(pairs), float(np.median(res)), rot_deg(A2), used))
            tt = f" t={frames[-1][2]:.2f} sig={frames[-1][3]:.1f}" if used else ""
            print(f"  {utc} n={len(pairs):2d} res={np.median(res):.2f} rot={rot_deg(A2):+.2f} sun={sun:+.0f} used={used}{tt}", flush=True)
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
fr = np.array([f[2:4] for f in frames])                  # t, sigma
sig_s = fr[:, 1] / fr[:, 0]                              # noise after scaling by 1/t
wf = 1 / sig_s ** 2                                      # = t^2 / sigma^2
neff = wf.sum() ** 2 / (wf ** 2).sum()
print(f"stacking {n} frames, effective {neff:.1f}; t {fr[:, 0].min():.2f}-{fr[:, 0].max():.2f}", flush=True)
out = {}
for k in "RGB":
    cube = np.stack(samples[k])
    med = np.median(cube, 0)
    mad = 1.4826 * np.median(np.abs(cube - med), 0)       # follows star cores, where frames disagree most
    keep = np.abs(cube - med) < 3 * np.maximum(mad[None], (sig_s / 3 ** 0.5)[:, None, None])
    W = keep * wf[:, None, None]
    out[k] = (cube * W).sum(0) / np.maximum(W.sum(0), 1e-12)
    out[k + "_eq"] = (cube * keep).sum(0) / np.maximum(keep.sum(0), 1)
    out[k + "_med"] = med
dest = os.path.expandvars(a.out) if a.out else f"{BASE}/eclipticam-frames/night/{a.night}/sword-stack.npz"
np.savez_compressed(dest, **out, n=n, cx=a.cx, cy=a.cy, ref=a.ref,
                    A_eps=np.array(sorted(As)), A_mats=np.array([As[k] for k in sorted(As)]),
                    log=np.array(log, dtype=object), frames=np.array(frames, dtype=object), neff=neff)
print("wrote", dest)
