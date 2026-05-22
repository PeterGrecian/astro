"""Plot distance vs days-before-now for the springcam scoring run."""
import csv
import datetime as dt
import matplotlib.pyplot as plt
from pathlib import Path

CSV = Path("/home/peter/photography/springcam/scripts/scores_spring_20260503_194114_l1_150px.csv")
HERO_EPOCH = dt.datetime(2026, 5, 3, 19, 41, 14, tzinfo=dt.timezone.utc).timestamp()
NOW = dt.datetime.now(tz=dt.timezone.utc)

xs, ys = [], []
hero_x = None
with CSV.open() as f:
    r = csv.DictReader(f)
    for row in r:
        ep = int(row["capture_epoch_utc"])
        captured = dt.datetime.fromtimestamp(ep, tz=dt.timezone.utc)
        days_before_now = -(NOW - captured).total_seconds() / 86400.0  # negative = past
        d = float(row["distance"])
        xs.append(days_before_now)
        ys.append(d)
        if abs(ep - HERO_EPOCH) < 60:
            hero_x = days_before_now

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(xs, ys, ".", markersize=2, alpha=0.4, color="#1f77b4")
if hero_x is not None:
    ax.axvline(hero_x, color="red", lw=0.8, alpha=0.6, label=f"hero (d=0 at x={hero_x:.1f})")
ax.set_xlabel("Days before now")
ax.set_ylabel("L1 distance to hero (mean abs diff, 0-255)")
ax.set_title(f"Springcam: distance to hero spring_20260503_194114.jpg vs days-before-now\n"
             f"3,486 frames, 2026-03-05 → 2026-05-15")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
out = Path("/tmp/springcam_distance.png")
fig.savefig(out, dpi=110)
print(f"saved {out}")
