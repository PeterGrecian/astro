#!/usr/bin/env python3
"""Neptune on eclipticam: whole-night stacks on the stars, then find the planet.

Neptune (V 7.8) is ~2.7 sigma in one 60 s frame, so each night is stacked:
every dark frame with Neptune in the field gets its own pointing fit local
to Neptune (check3.fit_frame, the Saturn method), is re-projected onto one
fixed patch of sky (gnomonic, GCRS axes, mid-exposure), and the night is an
inverse-variance, sigma-clipped mean. Neptune moves ~0.3 camera px a night,
so within a night it is a point; across nights it walks.

    cd ~/astro/scratch/saturn-walk && nohup ~/astro/.venv/bin/python neptune.py 2026-10-07 > nep.log 2>&1 &

Writes nep/<night>.npz (stack, weight, n, per-frame records).
"""
import glob, json, math, os, sys, warnings
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool

import numpy as np
from scipy.ndimage import map_coordinates

warnings.filterwarnings("ignore")
HERE = os.path.expanduser("~/astro/scratch/saturn-walk")
sys.path.insert(0, HERE)
import check3                                                    # noqa: E402
from check3 import BASE, LOC, P, model, _enu, fit_frame          # noqa: E402
import walk                                                      # noqa: E402
from astropy.coordinates import AltAz, GCRS, SkyCoord, get_body  # noqa: E402
from astropy.time import Time                                    # noqa: E402
import astropy.units as u                                        # noqa: E402

PLANET = os.environ.get("PLANET", "neptune")
if PLANET == "uranus":            # PLANET=uranus STARS_ALLSKY=1: Uranus near-stationary in Taurus, RA 63.4 -> 63.0 by 10-10
    RA0, DEC0, WDEG, HDEG = 63.4, 21.0, 3.0, 2.0   # tight: 18' of walk by 10-09; the V 4.9 star 0.9 deg east inside
    OUTD = f"{HERE}/ura"
else:
    RA0, DEC0 = 2.75, -0.25       # patch centre: Neptune 08-06..10-09 runs RA 4.1 -> 2.6; the V 6.3 star (RA 1.3) inside
    WDEG, HDEG = 4.2, 2.6
    OUTD = f"{HERE}/nep"
SCALE = 1.2 / 60                  # deg per patch px (camera ~3.5'/px)
W, H = 2304, 1296


def grid():
    w, h = int(WDEG / SCALE), int(HDEG / SCALE)
    X, Y = np.meshgrid((np.arange(w) - w / 2) * -math.radians(SCALE), (h / 2 - np.arange(h)) * math.radians(SCALE))
    a0, d0 = math.radians(RA0), math.radians(DEC0)
    den = math.cos(d0) - Y * math.sin(d0)
    return np.degrees(a0 + np.arctan2(X, den)), np.degrees(np.arctan2(math.sin(d0) + Y * math.cos(d0), np.hypot(X, den))), w, h


RA, DEC, GW, GH = grid()


def pick(night, p0):
    fr = []
    for p in glob.glob(f"{BASE}/{night}/v3w/[0-2][0-9]/*.fits.fz"):
        b = os.path.basename(p).split(".")[0]
        if len(b) == 13 and b.isdigit():
            fr.append((datetime.fromtimestamp(int(b) / 1000, timezone.utc), p))
    if not fr:
        return []
    fr.sort()
    ts = Time([t + timedelta(seconds=30) for t, _ in fr])
    fa = AltAz(obstime=ts, location=LOC, pressure=0)
    nep = get_body(PLANET, ts, LOC).transform_to(fa)
    sun = get_body("sun", ts, LOC).transform_to(fa)
    x, y = model(p0).project(_enu(np.radians(nep.az.deg), np.radians(nep.alt.deg)))
    ok = (nep.alt.deg > 20) & (sun.alt.deg < -12) & (x > 150) & (x < W - 150) & (y > 100) & (y < H - 150)
    return [fr[i] for i in np.where(ok)[0]]


def one(args):
    t, path, p0 = args
    try:
        r = fit_frame(t, path, p0, body=PLANET)
    except Exception as e:                                       # noqa: BLE001
        return dict(frame=os.path.basename(path), error=str(e)), None
    if r["n_stars"] < 10 or (r.get("near_med_px") or 9) > 1.2:
        return r, None
    img, exp = check3.load(path)
    noise = 1.4826 * np.median(np.abs(img - np.median(img)))
    tm = t + timedelta(seconds=exp / 2)
    sky = SkyCoord(RA.ravel() * u.deg, DEC.ravel() * u.deg, frame=GCRS(obstime=Time(tm)))
    aa = sky.transform_to(AltAz(obstime=Time(tm), location=LOC, pressure=0))
    x, y = model(dict(P, az0=r["az0"], alt0=r["alt0"], roll=r["roll"], f=r["f"])).project(
        _enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    patch = map_coordinates(img, [y, x], order=1, cval=np.nan).reshape(GH, GW).astype(np.float32)
    r["noise"] = float(noise)
    return r, patch


def stack(patches, noises):
    A = np.stack(patches); wts = 1 / np.array(noises) ** 2
    m = np.nanmedian(A, axis=0)
    s = 1.4826 * np.nanmedian(np.abs(A - m), axis=0)
    keep = np.abs(A - m) < 4 * np.maximum(s, 1e-6)
    Wt = np.where(keep & np.isfinite(A), wts[:, None, None], 0.0)
    S = (np.nan_to_num(A) * Wt).sum(0) / np.maximum(Wt.sum(0), 1e-12)
    return S.astype(np.float32), Wt.sum(0).astype(np.float32)


def main():
    os.makedirs(OUTD, exist_ok=True)
    sd = walk.seeds()
    for night in sys.argv[1:]:
        p0 = sd.get(night) or walk.registry_seed(night)
        fr = pick(night, p0)
        print(f"{night}: {len(fr)} frames with {PLANET} in the dark field", flush=True)
        recs, patches, noises = [], [], []
        with Pool(6) as pool:
            for r, patch in pool.imap(one, [(t, p, p0) for t, p in fr], chunksize=4):
                recs.append(r)
                if patch is not None:
                    patches.append(patch); noises.append(r["noise"])
        if len(patches) < (5 if PLANET == "uranus" else 10):   # Uranus (V 5.7) shows in a handful of frames
            print(f"{night}: only {len(patches)} usable frames, skipped", flush=True)
            continue
        S, Wsum = stack(patches, noises)
        np.savez_compressed(f"{OUTD}/{night}.npz", stack=S, weight=Wsum, n=len(patches),
                            recs=json.dumps(recs, default=float), ra0=RA0, dec0=DEC0, scale=SCALE)
        print(f"{night}: stacked {len(patches)} of {len(fr)}", flush=True)


if __name__ == "__main__":
    main()
