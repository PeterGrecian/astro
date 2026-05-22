#!/usr/bin/env python3
"""Plot brightness vs time from the scan CSV.

Two stacked panels:
  (1) mean, median, p95 traces over UTC time
  (2) bright_pixel count (pixels >= 500) per frame

Marks:
  - vertical lines: nautical/astronomical twilight end (yest) and
    astronomical/nautical twilight start (today)
  - red dots on the outlier frames (mean > median + k*MAD over a
    rolling window)
"""
import argparse, csv, sys
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()

rows = []
with open(args.csv) as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)
print(f"loaded {len(rows)} rows")

t = np.array([datetime.fromisoformat(r["iso_utc"]) for r in rows])
mean   = np.array([float(r["mean"])   for r in rows])
median = np.array([float(r["median"]) for r in rows])
p95    = np.array([float(r["p95"])    for r in rows])
bright = np.array([int(r["bright_pixels"]) for r in rows])

# Outlier detection: rolling-window median + MAD on mean.
W = 60   # +/- 30 frames either side = ~3 min window
def rolling_outliers(x, w=W, k=5.0):
    n = len(x)
    is_out = np.zeros(n, dtype=bool)
    for i in range(n):
        lo, hi = max(0, i - w//2), min(n, i + w//2)
        seg = x[lo:hi]
        m = np.median(seg)
        mad = np.median(np.abs(seg - m)) + 1e-6
        if abs(x[i] - m) > k * mad:
            is_out[i] = True
    return is_out

print("scanning for outliers...")
outliers = rolling_outliers(mean)
n_out = int(outliers.sum())
print(f"  outliers: {n_out} ({100*n_out/len(rows):.2f}%)")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                gridspec_kw={"height_ratios": [3, 1]})

ax1.plot(t, mean,   label="mean",   color="#4a9eff", linewidth=0.8)
ax1.plot(t, median, label="median", color="#34c759", linewidth=0.5, alpha=0.6)
ax1.plot(t, p95,    label="p95",    color="#ff9500", linewidth=0.5, alpha=0.7)
if n_out:
    ax1.scatter(t[outliers], mean[outliers], color="#ff3b30", s=4,
                label=f"outliers (n={n_out})", zorder=5)
ax1.set_ylabel("ADC value (0..1023)")
ax1.set_yscale("symlog", linthresh=10)
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(True, alpha=0.2)
ax1.set_title(f"starcam night brightness — {len(rows)} frames "
              f"{t[0].strftime('%Y-%m-%d %H:%M')} → {t[-1].strftime('%H:%M UTC')}")

ax2.plot(t, bright, color="#8e8e93", linewidth=0.6)
ax2.set_ylabel("bright px (>=500)")
ax2.set_yscale("symlog", linthresh=10)
ax2.grid(True, alpha=0.2)
ax2.xaxis.set_major_locator(mdates.HourLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax2.set_xlabel("UTC")

# Twilight markers (London, 2026-05-20/21)
# Astronomical twilight ends ~21:54 UTC, starts ~02:50 UTC
# Nautical ends ~20:54, starts ~03:50 (approx)
markers = [
    ("nautical end",    "2026-05-20T20:54", "#555"),
    ("astronomical end","2026-05-20T21:54", "#888"),
    ("astronomical start","2026-05-21T02:50","#888"),
    ("nautical start",  "2026-05-21T03:50", "#555"),
]
for label, iso, color in markers:
    dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    if t[0] <= dt <= t[-1]:
        for ax in (ax1, ax2):
            ax.axvline(dt, color=color, linestyle="--", linewidth=0.6, alpha=0.5)
        ax1.text(dt, ax1.get_ylim()[1]*0.7, label, rotation=90,
                 va="top", ha="right", fontsize=7, color=color, alpha=0.8)

plt.tight_layout()
plt.savefig(args.out, dpi=120)
print(f"wrote {args.out}")
