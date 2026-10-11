#!/usr/bin/env python3
"""Step 4: Saturn on every clear eclipticam night, 06-22 -> 10-09.

Per night: frames where Saturn is above 15 deg, the sun below -8 (Saturn is bright; July mornings need it) and Saturn's
predicted pixel well inside the frame; up to NPER of them, evenly spaced.
Each is fitted by check3.fit_frame (global then local pointing, Saturn masked,
planet measured against its neighbours), seeded from that night's pointing
in epochs-scan.csv, or the camera.json position_registry entry for its date.
Writes walk-frames.json (every frame) and walk-nights.csv (per-night medians).

Run on muppet (frames are there):
    cd ~/astro/scratch/saturn-walk && nohup ~/astro/.venv/bin/python walk.py > walk.log 2>&1 &
"""
import csv, glob, json, math, os, sys, warnings
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool

import numpy as np

warnings.filterwarnings("ignore")
HERE = os.path.expanduser("~/astro/scratch/saturn-walk")
sys.path.insert(0, HERE)
import check3                                                    # noqa: E402
from check3 import BASE, LOC, P, fit_frame, model                # noqa: E402
from astropy.coordinates import AltAz, get_body                  # noqa: E402
from astropy.time import Time                                    # noqa: E402
import astropy.units as u                                        # noqa: E402

D = math.radians
NPER = 12
FIRST, LAST = "2026-06-22", "2026-10-09"
W, H = 2304, 1296


def seeds():
    """night -> pointing dict: the night's own scan solution where it solved."""
    out = {}
    for r in csv.DictReader(open(f"{HERE}/epochs-scan.csv")):
        if int(r["n_good"]) >= 30 and float(r["med_px"]) < 1.3:
            out[r["night"]] = dict(P, az0=D(float(r["az0"])), alt0=D(float(r["alt0"])),
                                   roll=D(float(r["roll"])), f=float(r["f"]))
    return out


def registry_seed(night):
    reg = json.load(open(os.path.expanduser("~/astro/eclipticam-v3w/camera.json")))["position_registry"]
    best = None
    for k, e in sorted(reg.items(), key=lambda kv: int(kv[0])):
        start = e["dates"].split("..")[0][:10]
        if not start or start <= night:
            best = e["pointing"]
    return dict(P, az0=D(best["az0_deg"]), alt0=D(best["alt0_deg"]), roll=D(best["roll_deg"]), f=best["f_px"])


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
    sat = get_body("saturn", ts, LOC).transform_to(fa)
    sun = get_body("sun", ts, LOC).transform_to(fa)
    V = check3._enu(np.radians(sat.az.deg), np.radians(sat.alt.deg))
    x, y = model(p0).project(V)
    ok = (sat.alt.deg > 15) & (sun.alt.deg < -8) & (x > 150) & (x < W - 150) & (y > 100) & (y < H - 150)
    good = [fr[i] for i in np.where(ok)[0]]
    if not good:
        return []
    idx = np.linspace(0, len(good) - 1, min(NPER, len(good))).round().astype(int)
    return [good[i] for i in sorted(set(idx))]


def run_night(args):
    night, p0, src = args
    recs = []
    try:
        fr = pick(night, p0)
    except Exception as e:                                       # noqa: BLE001
        return night, src, [dict(night=night, error=f"pick: {e}")]
    for t, path in fr:
        try:
            r = fit_frame(t, path, p0)
        except Exception as e:                                   # noqa: BLE001
            r = dict(frame=os.path.basename(path), error=str(e), sat_found=False)
        r["night"], r["seed"] = night, src
        recs.append(r)
    return night, src, recs


def main():
    sd = seeds()
    nights = sorted(os.path.basename(n) for n in glob.glob(f"{BASE}/2026-*"))
    nights = [n for n in nights if FIRST <= n <= LAST and (len(sys.argv) < 2 or n in sys.argv[1:])]
    jobs = [(n, sd[n], "night") if n in sd else (n, registry_seed(n), "registry") for n in nights]
    allrec = []
    with Pool(4) as pool:
        for night, src, recs in pool.imap(run_night, jobs):
            allrec += recs
            found = [r for r in recs if r.get("sat_found")]
            seps = [r["sep_arcmin"] for r in found]
            print(f"{night} seed={src:8s} frames {len(recs)} found {len(found)}"
                  + (f"  sep med {np.median(seps):.2f}'" if seps else ""), flush=True)
            json.dump(allrec, open(f"{HERE}/walk-frames.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
