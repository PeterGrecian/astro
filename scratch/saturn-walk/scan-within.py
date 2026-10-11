#!/usr/bin/env python3
"""eclipticam pointing through the night, for the nights around each move.

The per-night scan (scan-epochs.py) fitted three frames near midnight; cloud
and missing nights leave the moves dated only to a gap of 2-6 nights. Here
every frame ~every 20 min is refined from each epoch's representative
solution and from the previous good frame, so a jump (a move) or a smooth
run (creep) shows in time order.

Run on muppet:  bigstore-run scratch/saturn-walk/scan-within.py > scan-within.log
"""
import glob, importlib.util, math, os, sys, warnings
from datetime import datetime, timedelta, timezone

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

warnings.filterwarnings("ignore")
HERE = os.path.expanduser("~/astro/scratch/saturn-walk")
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("scan_epochs", f"{HERE}/scan-epochs.py")
se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
from check3 import enu_of, STARS, P, BASE                         # noqa: E402

D = math.radians
# representative solutions per candidate epoch, from epochs-scan.csv
REPS = {
    "B2-0812": (200.439, 31.616, 3.780, 977.4),
    "C-0824": (199.731, 30.014, 2.647, 976.1),
    "D-0830": (199.215, 29.873, -0.369, 978.8),
    "E-0908": (199.856, 30.346, -0.702, 976.0),
    "F-0915": (199.769, 30.381, 0.124, 979.0),
    "F-0924": (199.434, 30.712, 1.407, 978.7),
    "G-1005": (199.210, 30.683, 1.745, 976.9),
    "1007": (199.255, 30.904, 1.651, 976.3),
}
SEEDS = {k: dict(P, az0=D(a), alt0=D(b), roll=D(c), f=f) for k, (a, b, c, f) in REPS.items()}
NIGHTS = ["2026-08-22", "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-28",
          "2026-09-06", "2026-09-07", "2026-09-08", "2026-09-13", "2026-09-14", "2026-09-15",
          "2026-09-16", "2026-09-17", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27",
          "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-06", "2026-10-07", "2026-10-08",
          "2026-10-09"]
STEP_S = 1200
OUTCSV = f"{HERE}/within-scan.csv"


def frames(night):
    fr = []
    for p in glob.glob(f"{BASE}/{night}/v3w/[0-2][0-9]/*.fits.fz"):
        b = os.path.basename(p).split(".")[0]
        if len(b) == 13 and b.isdigit():
            fr.append((datetime.fromtimestamp(int(b) / 1000, timezone.utc), p))
    fr.sort()
    out, last = [], None
    for t, p in fr:
        if last is None or (t - last).total_seconds() >= STEP_S:
            out.append((t, p)); last = t
    return out


def main():
    nights = [n for n in NIGHTS if len(sys.argv) < 2 or n in sys.argv[1:]]
    new = not os.path.exists(OUTCSV)
    with open(OUTCSV, "a") as f:
        if new:
            f.write("night,utc,start,n_good,med_px,az0,alt0,roll,f\n")
        for night in nights:
            prev = None
            for t, path in frames(night):
                img, exp = se.load(path)
                noise = 1.4826 * np.median(np.abs(img - np.median(img)))
                V = enu_of(SkyCoord(STARS[:, 0] * u.deg, STARS[:, 1] * u.deg), t + timedelta(seconds=exp / 2))
                starts = dict(SEEDS)
                if prev is not None:
                    starts["prev"] = prev
                best = None
                for name, p0 in starts.items():
                    n, med, p = se.refine(img, noise, V, p0)
                    if best is None or n > best[0]:
                        best = (n, med, p, name)
                n, med, p, name = best
                if n >= 30 and med < 1.3:
                    prev = p
                row = (f"{night},{t:%Y-%m-%dT%H:%M},{name},{n},{med:.2f},{math.degrees(p['az0']) % 360:.3f},"
                       f"{math.degrees(p['alt0']):.3f},{math.degrees(p['roll']):.3f},{p['f']:.1f}")
                f.write(row + "\n"); f.flush()
                print(row, flush=True)


if __name__ == "__main__":
    main()
