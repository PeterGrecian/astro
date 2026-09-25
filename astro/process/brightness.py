"""Per-frame brightness series for a night: CSV + log2 plot.

CSV columns match bin/scan-brightness so existing tooling can read it:
    epoch_ms, iso_utc, filename, mean, median, p95, max, bright_pixels

Plot conventions (GLOBAL.md / astro CLAUDE.md): x-axis in Europe/London,
y log base 2 so each gridline is one stop.
"""
import csv
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

LONDON = ZoneInfo("Europe/London")

HEADER = ["epoch_ms", "iso_utc", "filename",
          "mean", "median", "p95", "max", "bright_pixels"]

BRIGHT_PIXEL_THRESHOLD = 500

# --- raw bit-alignment -------------------------------------------------
# The Pi 5 ISP hands back 10-bit sensor raw left-shifted by 6 bits into a
# 16-bit container, so a frame reads either LSB-aligned (black ~64-76 ADU)
# or MSB-aligned (black ~4100-4900 = 64x). Which one you get has varied
# over the archive: of eclipticam-v3w's 76 nights, 9 are MSB-aligned
# (2026-06-09..13, 06-22, 08-17..19) and 67 are LSB — scattered, NOT a
# clean "before date X" boundary, so a date table would be wrong. Detect
# it from the data instead, the same self-describing trick
# bin/all-time-brightness uses for capture mode.
#
# Verified 2026-08-25: dividing each MSB night's series by 64 lands it
# squarely inside the LSB population (06-12 min 4574.4 -> 71.5; 08-17
# 4696.0 -> 73.4; 08-18 6249.1 -> 97.6, a night independently known to be
# 100% cloud) against an LSB range of 71.8-76. Left unnormalised these
# nights plot ~7.5 stops high and read as a sky 180x brighter than it was.
MSB_ALIGN_FACTOR = 64.0
MSB_ALIGN_MIN_ADU = 1000.0


# --- daylight rejection ------------------------------------------------
# Multi-night charts have to drop DAY captures: on cameras that run round
# the clock those land in the same noon-to-noon CSV, read saturated, and
# draw as a flat line across the top of the chart.
#
# The test is the SUN, not the clock. Until 2026-09-21 both cross-night
# charts hardcoded "local hour >= 21 or < 5", which is only ever right for
# one week of the year: by late September capture already starts at 20:12
# BST and runs to 06:10, so an hour of real twilight was discarded at each
# end BEFORE the axis was computed — and since the axis is derived from
# the data actually drawn, the chart lost the dusk fall and the dawn rise
# together. That is the bathtub: the per-night chart showed both walls and
# the combined chart showed only the flat bottom (Peter, 2026-09-21). It
# would have gone on worsening every week as the nights draw in, and in
# midwinter, with capture starting near 17:00, the filter would have
# thrown away half the night.
#
# Sun altitude is season-proof and is already how capture itself decides
# to start and stop (astro.state), so the chart and the capture gate now
# answer to the same physics. The default threshold matches state.py's
# civil-twilight day line; a camera's own `state.sun_altitude_day_deg`
# wins where it is set (astrocam: -8).
DEFAULT_DAY_ALT_DEG = -6.0


def daylight_keep_mask(times_local, cfg=None, day_alt_deg=None):
    """Boolean mask over `times_local`: True to KEEP the frame.

    Keeps everything captured with the sun at or below the camera's
    daytime altitude — all of night and both twilights, no daylight.
    Returns (mask, rule) where `rule` names which test was applied, so
    the caller can say so in its output.

    Falls back to the old clock window when the camera has no location
    or ephem is unavailable — the chart still draws, and says why.
    """
    times_local = list(times_local)
    loc = getattr(cfg, "location", None) if cfg is not None else None
    if day_alt_deg is None:
        state = (cfg.get("state") or {}) if cfg is not None else {}
        day_alt_deg = float(state.get("sun_altitude_day_deg")
                            or DEFAULT_DAY_ALT_DEG)
    if loc:
        try:
            from astro.state import sun_altitude_deg
            lat, lon = float(loc["lat_deg"]), float(loc["lon_deg"])
            # The sun moves ~0.25 deg a minute, far slower than the frame
            # cadence, so one altitude per minute is plenty and turns
            # thousands of ephem calls into hundreds.
            cache = {}
            mask = []
            for t in times_local:
                utc = t.astimezone(timezone.utc)
                key = utc.replace(second=0, microsecond=0)
                alt = cache.get(key)
                if alt is None:
                    alt = cache[key] = sun_altitude_deg(lat, lon, key)
                mask.append(alt <= day_alt_deg)
            return (np.array(mask, dtype=bool),
                    f"sun <= {day_alt_deg:g} deg")
        except (ImportError, KeyError, TypeError, ValueError) as exc:
            print(f"  daylight filter: sun altitude unavailable ({exc}); "
                  f"falling back to the 21:00-05:00 clock window")
    return (np.array([t.hour >= 21 or t.hour < 5 for t in times_local],
                     dtype=bool),
            "21:00-05:00 clock window (no location/ephem)")


def chart_zero(cfg) -> tuple[float | None, str]:
    """The ADU the brightness charts subtract before taking log2, and its
    axis label. Returns (value, label).

    The sensor's `black_level` where camera.json has one on the same
    per-frame LSB basis as the data, else the old `pedestal`. Stops are
    log2(mean - zero), so the zero has to be the real electronic zero:
    astrocam's pedestal of 50 sits 14 ADU below its measured black level
    of 64 and read ~0.84 stop high at the darkest (81.7 ADU: log2(31.7)
    vs log2(17.7)). Changed 2026-09-25 at mywebsite-keeper's request, on
    astro-science's measurement; `pedestal` stays in camera.json as the
    chart floor it was documented as, and is no longer subtracted here.

    Falls back to `pedestal` where black_level is on a DIFFERENT basis:
    eclipticam-v1's pedestal 10180 is a 10-coadd MSB container value
    while its black_level 15.9 is per frame, and starcam/xoverpi carry a
    per-frame black_level with no pedestal over co-added data. Those keep
    exactly what they drew before.
    """
    ped = cfg.get("pedestal")
    bl = cfg.get("black_level")
    if (ped is not None and bl is not None
            and float(ped) < MSB_ALIGN_MIN_ADU):
        return float(bl), "black level"
    return (float(ped) if ped is not None else None), "pedestal"


def lsb_align(vals, pedestal=None):
    """Normalise a night's mean-ADU series to LSB alignment.

    Returns (values, was_msb). Decided on the series MINIMUM, not the
    mean: the darkest frame is the closest thing to the sensor floor and
    is the least sensitive to how bright the night actually was. The two
    populations are three orders of magnitude apart, so the 1000 ADU cut
    is nowhere near either of them.

    `pedestal` (the camera's own black-level reference) DISARMS the test
    when it sits at or above the cut. The heuristic reads "a floor above
    1000 ADU means 10-bit raw left-shifted into a 16-bit container", which
    is a Pi-sensor fact, not a universal one: the Canon EOS 2000D writes
    14-bit raw with a black level of 2048, so every canon night looked
    MSB-aligned, got divided by 64 down to ~42 ADU, and fell BELOW its own
    pedestal — the whole archive collapsed onto the 0.5-count floor and
    drew as a dead flat line at -1.00 stops. Found 2026-09-21; canon
    retired on 2026-08-16, so nothing had republished its charts since the
    alignment rework of 08-25 and the last good render was still in S3.
    For every Pi camera the pedestal is ~50-105, far below the cut, so
    this guard changes nothing about which nights get normalised there.
    """
    vals = np.asarray(vals, dtype=float)
    if pedestal is not None and float(pedestal) >= MSB_ALIGN_MIN_ADU:
        return vals, False
    if vals.size == 0 or float(vals.min()) <= MSB_ALIGN_MIN_ADU:
        return vals, False
    return vals / MSB_ALIGN_FACTOR, True


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


def plot_night(rows, night: str, camera: str, out_path: Path,
               pedestal: float | None = None,
               stacked_window_utc: tuple[str, str] | None = None,
               zero_label: str = "pedestal"):
    """Scatter of log2(mean - pedestal) vs local time for one night's
    rows (as produced by measure()). X-axis ends at 05:00 the next
    morning (cover-close safety time), matching bin/plot-brightness.
    The timezone label is whatever Europe/London is on the night-of-date
    (BST or GMT), so it's never ambiguous.

    Y-axis is stops of signal ABOVE the sensor pedestal (electronic
    black level, exposed by libcamera's bit-shift unpack of 10-bit
    raw into the 16-bit container — typically a few thousand counts).
    `pedestal` is the per-sensor calibration constant (from camera.json);
    fall back to the night's 1st percentile if not given. With a fixed
    pedestal, 0 stops means "as dark as this sensor ever reads," each
    gridline is one stop of real signal."""
    times = [datetime.fromisoformat(r[1]).astimezone(LONDON) for r in rows]
    vals = np.array([float(r[3]) for r in rows])
    # Put MSB-aligned nights on the same ADU scale as everything else, so
    # the fixed pedestal from camera.json means the same thing on every
    # chart (see lsb_align).
    vals, _was_msb = lsb_align(vals, pedestal)
    if pedestal is None:
        pedestal = float(np.percentile(vals, 1))
    pedestal = float(pedestal)
    # 0.5-count floor (= log2 -1) prevents the -10 clip spikes when
    # mean ~= pedestal; real lens-covered drops still go negative.
    signal = np.maximum(vals - pedestal, 0.5)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.scatter(times, signal, s=3, linewidths=0, color="#007AFF")
    ax.set_yscale("log", base=2)
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda y, _pos: f"{math.log2(y):.0f}" if y > 0 else ""))
    night_date = datetime.strptime(night, "%Y-%m-%d").date()
    tz_label = datetime.combine(
        night_date, time(22, 0), tzinfo=LONDON).tzname()
    ax.set_xlabel(f"local time ({tz_label})")
    ax.set_ylabel(f"stops above {zero_label} ({pedestal:.0f})")
    ax.set_title(f"{camera} — night {night} — per-frame brightness")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%H:%M", tz=LONDON))
    # 21:00 (night N) -> 05:00 next morning. The 05:00 local cover-close
    # safety close is the rightmost event we expect to see.
    #
    # LEFT EDGE IS 21:00, NOT 22:00 (changed 2026-08-25, Peter): capture
    # starts when the sun reaches the camera's night altitude, which in
    # late August is ~20:12 UTC = 21:12 local — so a 22:00 left edge
    # silently CLIPPED the first ~48 min of every night, including the
    # steep twilight fall-off where the measurements visibly begin.
    # Verified the same on both published cameras (astrocam and
    # eclipticam-v3w both first-framed at 20:12:04 UTC on 2026-08-24).
    # bin/combined-brightness admits h >= 21 in its observing-window
    # filter, so 21:00 also makes the per-night and multi-night charts
    # agree on where the night starts.
    # BOTH EDGES ARE DYNAMIC (Peter, 2026-08-25): the whole hour either
    # side of the data actually present, rather than a fixed window.
    #
    # This supersedes both the old hard 22:00->05:00 frame and the fixed
    # 21:00 that briefly replaced its left edge. A fixed frame is wrong in
    # both directions at once: 05:00 clipped the dawn rise mid-climb on
    # nights that ran past it, and any fixed left edge is a midwinter bug
    # in waiting, because capture tracks the sun and starts hours earlier
    # in December than in August. Deriving the frame from the data cannot
    # clip and cannot leave a broad empty margin on a short night.
    #
    # Late-August nights land on 21:00 of their own accord (frames start
    # ~21:12), so this gives the 9pm start that prompted the change while
    # still being right in every other season.
    start = datetime.combine(night_date, time(21, 0), tzinfo=LONDON)
    end = datetime.combine(night_date + timedelta(days=1),
                           time(5, 0), tzinfo=LONDON)
    if times:
        first, last = min(times), max(times)
        start = first.replace(minute=0, second=0, microsecond=0)
        floor_last = last.replace(minute=0, second=0, microsecond=0)
        end = floor_last + timedelta(hours=1) if floor_last < last else last
    ax.set_xlim(start, end)
    # Mark the time-range of frames that entered max/min/sum stacks.
    # These bounds come from nightly-cam's anchor-band gate; everything
    # outside is twilight, dawn, or unusually-dark flap frames.
    if stacked_window_utc:
        try:
            t_lo = datetime.fromisoformat(stacked_window_utc[0]).astimezone(LONDON)
            t_hi = datetime.fromisoformat(stacked_window_utc[1]).astimezone(LONDON)
            for t in (t_lo, t_hi):
                ax.axvline(t, color="#FF9500", linestyle="--",
                           linewidth=1.2, alpha=0.7)
        except (ValueError, TypeError):
            pass
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, facecolor="white")
    plt.close(fig)


def find_night_csvs(cfg):
    """Yield (night_str, csv_path) for every per-night brightness CSV.

    Three layouts are live at once, so this is the single place that
    knows them. Lifted out of bin/combined-brightness 2026-08-24 when
    bin/all-time-brightness needed the same walk — the edge cases below
    are the kind that rot if copied.
    """
    name = "brightness.csv"
    # Canonical layout: <root>/YYYY/MM/DD/<camera>/brightness.csv
    if cfg.night_layout == "canonical":
        root = cfg.frames_root
        if root.exists():
            for y in sorted(p for p in root.iterdir() if p.name.isdigit()):
                for m in sorted(p for p in y.iterdir() if p.name.isdigit()):
                    for d in sorted(p for p in m.iterdir() if p.name.isdigit()):
                        csv_p = d / cfg.name / name
                        if csv_p.exists():
                            yield f"{y.name}-{m.name}-{d.name}", csv_p
        return
    nights_root = cfg.frames_root / "night"
    if not nights_root.exists():
        # astrocam-style flat layout: look directly under frames_root
        for d in sorted(cfg.frames_root.iterdir()):
            csv_p = d / name
            if csv_p.exists() and d.name[:4].isdigit():
                yield d.name, csv_p
        return
    # percam legacy tree: brightness.csv lives at the night level. Naming
    # changed mid-migration — newer nights use plain "brightness.csv",
    # older ones the subcam-prefixed "<subcam>_brightness.csv" (e.g.
    # v3w_brightness.csv). Accept both so pre-migration reference nights
    # (e.g. the dark 2026-06-10) still plot.
    subcam = cfg.name.split("-", 1)[1] if "-" in cfg.name else cfg.name
    for d in sorted(nights_root.iterdir()):
        for cand in (d / name, d / f"{subcam}_{name}"):
            if cand.exists():
                yield d.name, cand
                break


def darkest_anchor(times_per_s, window_s: float = 600.0):
    """The median brightness over the darkest contiguous `window_s`
    of the night — the "typical dark frame" anchor. Returns
    (anchor_per_s, anchor_start_utc, anchor_end_utc) or None.

    times_per_s: list of (utc_datetime, per_s) — per_s is the brightness
    quality metric mean/(EXPTIME*GAIN), already computed by the caller.

    10 min is long enough that a single bad frame can't drag the anchor
    off, short enough that twilight can't creep in. Good for automation:
    one knob (window length), no per-camera threshold.
    """
    pts = sorted(times_per_s)
    if len(pts) < 2:
        return None
    times = [p[0] for p in pts]
    vals = np.array([p[1] for p in pts])
    best = None  # (median_per_s, start_utc, end_utc)
    j = 0
    for i in range(len(pts)):
        while j < len(pts) and (times[j] - times[i]).total_seconds() <= window_s:
            j += 1
        n = j - i
        if n < 2:
            continue
        med = float(np.median(vals[i:j]))
        if best is None or med < best[0]:
            best = (med, times[i], times[j - 1])
    return best


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
