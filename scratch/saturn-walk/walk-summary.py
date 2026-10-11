#!/usr/bin/env python3
"""Per-night Saturn from walk-frames.json: quality-filtered medians, the
measured track against the ephemeris, and a check plot (walk-check.png)."""
import csv, json, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
fr = json.load(open(f"{HERE}/walk-frames.json"))


def good(r):
    return (r.get("sat_found") and r["n_stars"] >= 10 and (r.get("near_med_px") or 9) < 1.2
            and r["sat_peak_sigma"] >= 30)


def resid(r):
    c = math.cos(math.radians(r["eph_dec"]))
    return (r["meas_ra"] - r["eph_ra"]) * c * 60, (r["meas_dec"] - r["eph_dec"]) * 60


def agree(g, tol=4.0):
    """frames within tol arcmin of the night's median residual (a bad pointing fit is an outlier, not noise)"""
    if not g:
        return g
    d = np.array([resid(r) for r in g]); m = np.median(d, axis=0)
    return [r for r, v in zip(g, d) if np.hypot(*(v - m)) < tol]


nights = sorted({r["night"] for r in fr})
rows = []
for n in nights:
    rs = [r for r in fr if r["night"] == n]
    g = agree([r for r in rs if good(r)])
    if len(g) < 3:
        rows.append(dict(night=n, frames=len(rs), good=len(g), ok=False))
        continue
    c = math.cos(math.radians(np.median([r["eph_dec"] for r in g])))
    dra = np.array([(r["meas_ra"] - r["eph_ra"]) * c * 60 for r in g])
    ddec = np.array([(r["meas_dec"] - r["eph_dec"]) * 60 for r in g])
    sep = np.array([r["sep_arcmin"] for r in g])
    rows.append(dict(night=n, frames=len(rs), good=len(g), ok=True,
                     dra=float(np.median(dra)), ddec=float(np.median(ddec)), sep=float(np.median(sep)),
                     scatter=float(1.4826 * np.median(np.abs(sep - np.median(sep)))),
                     ra=float(np.median([r["meas_ra"] for r in g])), dec=float(np.median([r["meas_dec"] for r in g])),
                     eph_ra=float(np.median([r["eph_ra"] for r in g])), eph_dec=float(np.median([r["eph_dec"] for r in g])),
                     t_mid=sorted(r["t_mid"] for r in g)[len(g) // 2]))
with open(f"{HERE}/walk-nights.csv", "w") as f:
    keys = ["night", "frames", "good", "ok", "t_mid", "ra", "dec", "eph_ra", "eph_dec", "dra", "ddec", "sep", "scatter"]
    w = csv.DictWriter(f, keys); w.writeheader()
    for r in rows:
        w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items() if k in keys})
ok = [r for r in rows if r["ok"]]
print(f"{len(nights)} nights with Saturn frames, {len(ok)} measured (>=3 good frames)")
print(f"residual vs ephemeris: dRA*cos median {np.median([r['dra'] for r in ok]):+.2f}'  "
      f"dDec {np.median([r['ddec'] for r in ok]):+.2f}'  sep median {np.median([r['sep'] for r in ok]):.2f}' "
      f"p90 {np.percentile([r['sep'] for r in ok], 90):.2f}'")
for r in ok:
    flag = "  <--" if r["sep"] > 5 else ""
    print(f"  {r['night']} {r['good']:2d}/{r['frames']:2d}  RA {r['ra']:8.4f} Dec {r['dec']:+7.4f}  "
          f"d=({r['dra']:+5.2f},{r['ddec']:+5.2f})'  sep {r['sep']:.2f}' +/-{r['scatter']:.2f}{flag}")

fig, ax = plt.subplots(1, 2, figsize=(14, 5))
er = [r["eph_ra"] for r in ok]; ed = [r["eph_dec"] for r in ok]
ax[0].plot(er, ed, "-", color="#999", label="ephemeris (same instants)")
sc = ax[0].scatter([r["ra"] for r in ok], [r["dec"] for r in ok], c=range(len(ok)), cmap="viridis", s=14, label="measured")
ax[0].invert_xaxis(); ax[0].set_xlabel("RA (deg, GCRS)"); ax[0].set_ylabel("Dec (deg)"); ax[0].legend()
ax[0].set_title("Saturn: measured per night vs ephemeris")
from datetime import date
dd = [date.fromisoformat(r["night"]) for r in ok]
ax[1].plot(dd, [r["dra"] for r in ok], "o", ms=4, label="dRA cos(dec)")
ax[1].plot(dd, [r["ddec"] for r in ok], "s", ms=4, label="dDec")
ax[1].axhline(0, color="#999"); ax[1].set_ylabel("measured - ephemeris (arcmin)"); ax[1].legend()
ax[1].set_title("residual per night (1 px ~ 3.5')"); fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(f"{HERE}/walk-check.png", dpi=80)
