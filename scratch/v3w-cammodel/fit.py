#!/usr/bin/env python3
"""eclipticam-v3w camera model for epoch 7 (moved 2026-10-13), fitted on 2026-10-29.

Method as the 10-07 model (astro 20397b9): equidistant + cubic about the
optical axis (astro/skyglow.py CameraModel), binned 2304x1296, fitted against
Hipparcos V<7.5. Differences:
  * the ALL-SKY list (hip75-allsky.npy). The 10-07 model's 6844 stars stop at
    RA ~60 deg, so Taurus/Orion, in the east of the field after midnight in
    late October, had no catalogue stars at all;
  * a joint fit over several frames of the clean window: lens (f, k, cx, cy)
    shared, pointing (az0, alt0, roll) per frame, so the fit is not one-frame
    (a one-frame refine leaves a U-shaped drift through the night).
The written pointing is the fit at the frame nearest REF (mid-window).

Run on muppet:  bigstore-run scratch/v3w-cammodel/fit.py [NIGHT]
"""
import json, math, os, sys, warnings
from datetime import timedelta

os.environ["STARS_ALLSKY"] = "1"
import numpy as np
from scipy.optimize import least_squares

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import check3                                                     # noqa: E402
from check3 import _proj, centroid, enu_of, STARS, VMAG, P        # noqa: E402
from astropy.coordinates import SkyCoord                          # noqa: E402
import astropy.units as u                                         # noqa: E402

NIGHT = sys.argv[1] if len(sys.argv) > 1 else "2026-10-29"
T0, T1, REF = (sys.argv[2:5] if len(sys.argv) > 4 else ("00:00", "02:00", "01:00"))
check3.NPER = 7
os.makedirs(os.path.expanduser("~/tmp/v3w-cammodel"), exist_ok=True)
OUT = os.path.expanduser(f"~/tmp/v3w-cammodel/cammodel-{NIGHT}.json")
D = math.radians
SC = SkyCoord(STARS[:, 0] * u.deg, STARS[:, 1] * u.deg)

frames = check3.frames(NIGHT, check3.utc(NIGHT, T0), check3.utc(NIGHT, T1))
print(f"{NIGHT}: {len(frames)} frames {T0}-{T1} UTC", flush=True)
data = []
for t, path in frames:
    img, exp = check3.load(path)
    noise = 1.4826 * np.median(np.abs(img - np.median(img)))
    V = enu_of(SC, t + timedelta(seconds=exp / 2))
    data.append(dict(t=t, path=path, img=img, noise=noise, V=V))

from scipy.ndimage import maximum_filter                          # noqa: E402

LENS = ["f", "k", "cx", "cy"]
lens = np.array([P[k] for k in LENS])
mirror = P["mirror"]


def coarse(d, q):
    """Best pointing nudge for one frame: shift grid, then a small roll/scale-free
    pattern score. Returns pixel shift (dx, dy)."""
    img, V = d["img"], d["V"]
    H, W = img.shape
    sm = maximum_filter(np.clip(img / d["noise"], 0, 50), size=3)
    x, y, th = _proj(V, *q, *lens, mirror)
    inb = (x > 60) & (x < W - 60) & (y > 60) & (y < H - 60) & (V[:, 2] > 0.17) & (th < D(70))
    xi, yi = np.round(x[inb]).astype(int), np.round(y[inb]).astype(int)
    best = (-1, 0, 0)
    for dy in range(-60, 61, 2):
        for dx in range(-60, 61, 2):
            yy, xx = yi + dy, xi + dx
            ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
            s = sm[yy[ok], xx[ok]].sum()
            if s > best[0]:
                best = (s, dx, dy)
    return best[1], best[2]


def match(d, q, lens_, r, shift=(0, 0)):
    img, V = d["img"], d["V"]
    H, W = img.shape
    x, y, th = _proj(V, *q, *lens_, mirror)
    inb = (x > 30) & (x < W - 30) & (y > 30) & (y < H - 30) & (V[:, 2] > 0.17) & (th < D(75))
    meas, keep = [], []
    for i in np.where(inb)[0]:
        c = centroid(img, x[i] + shift[0], y[i] + shift[1], r, d["noise"])
        if c is not None:
            meas.append(c[:2]); keep.append(i)
    return np.array(meas), np.array(keep, int)


# 0. blind pointing search on the mid-window frame (epoch 7 moved by more than
#    a pixel shift can absorb: the 10-07 seed matches < 15 stars on any night)
imid = len(data) // 2
g = check3.grid_pointing(data[imid]["img"], data[imid]["noise"], data[imid]["V"], dict(P))
SEED = np.array([g["az0"], g["alt0"], g["roll"]])

# 1. per-frame pointing (az0, alt0, roll) from the grid seed, lens fixed
pts = []
for d in data:
    q = SEED.copy()
    sh = coarse(d, q)
    for r in (8, 5, 3):
        meas, keep = match(d, q, lens, r, sh)
        def res(qq):
            x, y, _ = _proj(d["V"][keep], *qq, *lens, mirror)
            return np.concatenate([x - meas[:, 0], y - meas[:, 1]])
        s = least_squares(res, q, loss="soft_l1", f_scale=1.0)
        q, sh = s.x, (0, 0)
    dd = np.hypot(*np.split(s.fun, 2))
    print(f"  {d['t']:%H:%M} pointing-only: n {len(keep)}  median {np.median(dd):.2f} px", flush=True)
    pts.append(q)

# 2. joint fit: shared lens, per-frame pointing; iterate match radius
NF = len(data)
x0 = np.concatenate([lens, np.concatenate(pts)])
for r in (4, 3, 2):
    L, Q = x0[:4], x0[4:].reshape(NF, 3)
    M = [match(d, Q[i], L, r) for i, d in enumerate(data)]

    def res(xx):
        L, Q = xx[:4], xx[4:].reshape(NF, 3)
        out = []
        for i, d in enumerate(data):
            meas, keep = M[i]
            x, y, _ = _proj(d["V"][keep], *Q[i], *L, mirror)
            out += [x - meas[:, 0], y - meas[:, 1]]
        return np.concatenate(out)

    s = least_squares(res, x0, loss="soft_l1", f_scale=0.7, x_scale="jac")
    x0 = s.x
    meds = []
    o = 0
    for meas, keep in M:
        n = len(keep)
        dx, dy = s.fun[o:o + n], s.fun[o + n:o + 2 * n]
        o += 2 * n
        meds.append((n, float(np.median(np.hypot(dx, dy)))))
    print(f"  joint r={r}: lens f {x0[0]:.1f} k {x0[1]:.4f} c ({x0[2]:.1f},{x0[3]:.1f});"
          f" per frame n/median {[(n, round(m, 2)) for n, m in meds]}", flush=True)

L, Q = x0[:4], x0[4:].reshape(NF, 3)
iref = int(np.argmin([abs((d["t"] - check3.utc(NIGHT, REF)).total_seconds()) for d in data]))

# residual by radius (does k hold to the corners?) at the reference frame
d = data[iref]
meas, keep = match(d, Q[iref], L, 2)
x, y, th = _proj(d["V"][keep], *Q[iref], *L, mirror)
rr = np.hypot(x - meas[:, 0], y - meas[:, 1])
for lo, hi in ((0, 20), (20, 35), (35, 50), (50, 75)):
    m = (np.degrees(th) >= lo) & (np.degrees(th) < hi)
    if m.any():
        print(f"  off-axis {lo:2d}-{hi:2d} deg: n {m.sum():3d}  median {np.median(rr[m]):.2f} px", flush=True)
dq = np.degrees(Q - Q[iref])
print(f"  pointing drift over window (deg, vs ref): az {dq[:,0].min():+.3f}..{dq[:,0].max():+.3f}"
      f" alt {dq[:,1].min():+.3f}..{dq[:,1].max():+.3f} roll {dq[:,2].min():+.3f}..{dq[:,2].max():+.3f}", flush=True)

# star list for derot-sky refine: Hipparcos V<7.5 within 65 deg of the axis
from astro.skyglow import _enu                                    # noqa: E402
ax = _enu(np.array(Q[iref][0]), np.array(Q[iref][1]))
near = np.degrees(np.arccos(np.clip(d["V"] @ ax, -1, 1))) < 65
out = {k: P[k] for k in ("lat", "lon")}
out.update(mirror=mirror, az0=float(Q[iref][0]), alt0=float(Q[iref][1]), roll=float(Q[iref][2]),
           f=float(L[0]), k=float(L[1]), cx=float(L[2]), cy=float(L[3]),
           model_note=P["model_note"], fit_night=NIGHT, fit_frame=d["path"],
           fit_utc=d["t"].isoformat(), fit_median_px=float(np.median(rr)), fit_n=int(len(keep)),
           fit_frames=[dd["path"] for dd in data],
           fit_method=("joint fit, lens shared and pointing per frame, over "
                       f"{NF} frames {T0}-{T1} UTC; Hipparcos V<7.5 all-sky (VizieR I/239); "
                       "seeded from cammodel-2026-10-07; astro-science 2026-11-10, "
                       "scratch/v3w-cammodel/fit.py"),
           stars_radec_j2000=[[float(a), float(b_)] for a, b_ in STARS[near]],
           stars_note="Hipparcos V<7.5, ALL-SKY list (includes Taurus/Orion, which the 10-07 list lacked), "
                      "within 65 deg of the field centre at the fit frame")
json.dump(out, open(OUT, "w"), indent=1)
print(f"  -> {OUT}  (pointing az {math.degrees(out['az0']):.3f} alt {math.degrees(out['alt0']):.3f}"
      f" roll {math.degrees(out['roll']):.3f}; {near.sum()} catalogue stars)", flush=True)
