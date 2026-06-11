"""Per-frame brightness series for a night: CSV + log2 plot.

CSV columns match bin/scan-brightness so existing tooling can read it:
    epoch_ms, iso_utc, filename, mean, median, p95, max, bright_pixels

Plot conventions (GLOBAL.md / astro CLAUDE.md): x-axis in Europe/London,
y log base 2 so each gridline is one stop.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

LONDON = ZoneInfo("Europe/London")

HEADER = ["epoch_ms", "iso_utc", "filename",
          "mean", "median", "p95", "max", "bright_pixels"]

BRIGHT_PIXEL_THRESHOLD = 500


def measure(arr, t_utc: datetime, path: Path):
    """One CSV row for a frame already in memory."""
    return [int(t_utc.timestamp() * 1000), t_utc.isoformat(), str(path),
            f"{float(arr.mean()):.3f}", f"{float(np.median(arr)):.1f}",
            f"{float(np.percentile(arr, 95)):.1f}", int(arr.max()),
            int((arr >= BRIGHT_PIXEL_THRESHOLD).sum())]


def write_csv(rows, csv_path: Path):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def read_csv(csv_path: Path):
    """Return list of (utc_datetime, mean) from a brightness CSV."""
    out = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.fromisoformat(row["iso_utc"])
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                out.append((t, float(row["mean"])))
            except (KeyError, ValueError):
                continue
    out.sort()
    return out


def plot_night(rows, night: str, camera: str, out_path: Path):
    """Scatter of log2(mean) vs local time for one night's rows
    (as produced by measure())."""
    times = [datetime.fromisoformat(r[1]).astimezone(LONDON) for r in rows]
    vals = np.array([float(r[3]) for r in rows])
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.scatter(times, np.maximum(vals, 1e-3), s=3, linewidths=0,
               color="#007AFF")
    ax.set_yscale("log", base=2)
    ax.set_xlabel("local time (Europe/London, GMT/BST)")
    ax.set_ylabel("mean ADU (log2)")
    ax.set_title(f"{camera} — night {night} — per-frame brightness")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%H:%M", tz=LONDON))
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, facecolor="white")
    plt.close(fig)


def darkest_window(rows, window_s: float):
    """(start_utc, end_utc) of the contiguous window of length window_s
    with the lowest mean brightness, or None if the night is shorter
    than the window. rows as produced by measure()."""
    if len(rows) < 2:
        return None
    pts = sorted((datetime.fromisoformat(r[1]), float(r[3])) for r in rows)
    times = [p[0] for p in pts]
    vals = np.array([p[1] for p in pts])
    if (times[-1] - times[0]).total_seconds() < window_s:
        return times[0], times[-1]
    best = None
    j = 0
    csum = np.concatenate([[0.0], np.cumsum(vals)])
    for i in range(len(pts)):
        while j < len(pts) and (times[j] - times[i]).total_seconds() <= window_s:
            j += 1
        n = j - i
        if n < 2:
            continue
        mean = (csum[j] - csum[i]) / n
        if best is None or mean < best[0]:
            best = (mean, times[i], times[j - 1])
    if best is None:
        return None
    return best[1], best[2]
