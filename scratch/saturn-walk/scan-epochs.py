#!/usr/bin/env python3
"""eclipticam pointing per night, June -> October: find the epoch boundaries.

For every night, the clearest of three frames near local midnight is refined
(az0, alt0, roll, f; lens k/centre fixed from the 10-07 solve) against
Hipparcos V<7.5, starting from each known seed (the 10-07 model, the 08-12
rose-bush bootstrap, the 09-05 bootstrap) and from the previous night's
solution. The best start wins. A jump in az0/alt0/roll between nights is a
move; a night where no start fits is cloud or a big move (bootstrap later).

Run on muppet:  bigstore-run scratch/saturn-walk/scan-epochs.py
"""
import glob, json, math, os, sys, warnings
from datetime import datetime, timedelta, timezone

import numpy as np
from astropy.io import fits
from scipy.ndimage import maximum_filter, zoom
from scipy.optimize import least_squares

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import check3                                                    # noqa: E402
from check3 import _proj, centroid, enu_of, STARS, P             # noqa: E402
from astropy.coordinates import SkyCoord                         # noqa: E402
import astropy.units as u                                        # noqa: E402

D = math.radians
SEEDS = {
    "10-07": dict(P),
    "rosebush": dict(P, az0=D(200.48), alt0=D(31.86), roll=D(3.59), f=976.0),
    "09-05": dict(P, az0=D(199.23), alt0=D(29.97), roll=D(-0.82), f=978.5),
}
TIMES = ("23:00", "00:15", "01:30")      # UTC, dark all season
OUTCSV = f"{check3.OUT}/epochs-scan.csv"


def load(path):
    with fits.open(path) as h:
        d = h[1].data.astype(np.float32)
        exp = float(h[1].header.get("EXPTIME", 59.9))
    H, W = d.shape
    b = d if W <= 2304 else d[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2).sum(axis=(1, 3))
    B = 32
    h2, w2 = b.shape[0] // B, b.shape[1] // B
    med = np.median(b[:h2 * B, :w2 * B].reshape(h2, B, w2, B).transpose(0, 2, 1, 3).reshape(h2, w2, -1), axis=2)
    return b - zoom(med, (b.shape[0] / h2, b.shape[1] / w2), order=1), exp


def pick_frames(night):
    fr = []
    for p in glob.glob(f"{check3.BASE}/{night}/v3w/[0-2][0-9]/*.fits.fz"):
        b = os.path.basename(p).split(".")[0]
        if len(b) == 13 and b.isdigit():
            fr.append((datetime.fromtimestamp(int(b) / 1000, timezone.utc), p))
        elif p.split("/")[-2] in ("23", "00", "01"):
            # early June: sequence-numbered files; time from the header
            try:
                d = fits.getheader(p, 1).get("DATE-OBS")
                t = datetime.fromisoformat(d.replace("Z", "")).replace(tzinfo=timezone.utc)
                fr.append((t, p))
            except Exception:
                pass
    out = []
    for hm in TIMES:
        t0 = check3.utc(night, hm)
        if fr:
            t, p = min(fr, key=lambda tp: abs((tp[0] - t0).total_seconds()))
            if abs((t - t0).total_seconds()) < 1200:
                out.append((t, p))
    return out


def refine(img, noise, V, p):
    """Coarse pixel shift, then two match/fit passes. Returns (n, median px, p)."""
    H, W = img.shape
    sm = maximum_filter(np.clip(img / noise, 0, 50), size=3)
    x, y, th = _proj(V, p["az0"], p["alt0"], p["roll"], p["f"], p["k"], p["cx"], p["cy"], p["mirror"])
    inb = (x > 60) & (x < W - 60) & (y > 60) & (y < H - 60) & (V[:, 2] > 0.2) & (th < D(70))
    if inb.sum() < 20:
        return 0, 99.0, p
    xi, yi = np.round(x[inb]).astype(int), np.round(y[inb]).astype(int)
    best = (-1, 0, 0)
    for dy in range(-30, 31, 2):
        for dx in range(-30, 31, 2):
            yy, xx = yi + dy, xi + dx
            ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
            sc = sm[yy[ok], xx[ok]].sum()
            if sc > best[0]:
                best = (sc, dx, dy)
    q = np.array([p["az0"], p["alt0"], p["roll"], p["f"]])
    sh = best[1:]
    for r in (6, 3):
        x, y, _ = _proj(V, *q, p["k"], p["cx"], p["cy"], p["mirror"])
        meas, keep = [], []
        for i in np.where(inb)[0]:
            c = centroid(img, x[i] + sh[0], y[i] + sh[1], r, noise)
            if c is not None:
                meas.append(c[:2]); keep.append(i)
        if len(keep) < 12:
            return len(keep), 99.0, p
        meas, keep = np.array(meas), np.array(keep)

        def resid(qq):
            xx, yy, _ = _proj(V[keep], *qq, p["k"], p["cx"], p["cy"], p["mirror"])
            return np.concatenate([xx - meas[:, 0], yy - meas[:, 1]])

        s = least_squares(resid, q, loss="soft_l1", f_scale=1.0)
        q, sh = s.x, (0, 0)
    d = np.hypot(*np.split(s.fun, 2))
    good = int((d < 2).sum())
    return good, float(np.median(d)), dict(p, az0=float(q[0]), alt0=float(q[1]), roll=float(q[2]), f=float(q[3]))


def main():
    nights = sorted(os.path.basename(n) for n in glob.glob(f"{check3.BASE}/2026-*"))
    nights = [n for n in nights if len(sys.argv) < 2 or n >= sys.argv[1]]
    prev = None
    with open(OUTCSV, "w") as f:
        f.write("night,utc,start,n_good,med_px,az0,alt0,roll,f\n")
        for night in nights:
            best = None
            for t, path in pick_frames(night):
                img, exp = load(path)
                noise = 1.4826 * np.median(np.abs(img - np.median(img)))
                V = enu_of(SkyCoord(STARS[:, 0] * u.deg, STARS[:, 1] * u.deg), t + timedelta(seconds=exp / 2))
                starts = dict(SEEDS)
                if prev is not None:
                    starts["prev"] = prev
                for name, p0 in starts.items():
                    n, med, p = refine(img, noise, V, p0)
                    if best is None or n > best[0]:
                        best = (n, med, p, name, t)
            if best is None:
                print(f"{night} no frames", flush=True)
                continue
            n, med, p, name, t = best
            ok = n >= 30 and med < 1.3
            if ok:
                prev = p
            row = (f"{night},{t:%H:%M},{name},{n},{med:.2f},{math.degrees(p['az0']) % 360:.3f},"
                   f"{math.degrees(p['alt0']):.3f},{math.degrees(p['roll']):.3f},{p['f']:.1f}")
            f.write(row + "\n"); f.flush()
            print(row + ("" if ok else "   <- unsolved"), flush=True)


if __name__ == "__main__":
    main()
