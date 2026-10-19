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
from matplotlib.ticker import FuncFormatter, FormatStrFormatter, MultipleLocator, NullLocator
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

LONDON = ZoneInfo("Europe/London")

HEADER = ["epoch_ms", "iso_utc", "filename",
          "mean", "median", "p95", "max", "bright_pixels", "exptime",
          "box_temp_c", "box_rh_pct", "senstemp_c", "cover"]

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


def measure(arr, t_utc: datetime, path: Path, exptime: float | None = None,
            box_temp_c: float | None = None,
            box_rh_pct: float | None = None,
            senstemp_c: float | None = None,
            cover: str | None = None):
    """One CSV row for a frame already in memory.

    exptime (s, from the frame's EXPTIME) is the exposure time.
    box_temp_c, box_rh_pct, senstemp_c, cover: environmental and hardware
    sidecars when available (DHT22 enclosure temp/RH, IMX708 sensor temp,
    and SG90 transparent cover open/closed state). Readers index positionally
    up to mean/median only, so appending is safe.
    """
    row = [int(t_utc.timestamp() * 1000), t_utc.isoformat(), str(path),
           f"{float(arr.mean()):.3f}", f"{float(np.median(arr)):.1f}",
           f"{float(np.percentile(arr, 95)):.1f}", int(arr.max()),
           int((arr >= BRIGHT_PIXEL_THRESHOLD).sum()),
           "" if exptime is None else f"{float(exptime):g}"]
    row.extend([
        "" if box_temp_c is None else f"{float(box_temp_c):.1f}",
        "" if box_rh_pct is None else f"{float(box_rh_pct):.1f}",
        "" if senstemp_c is None else f"{float(senstemp_c):.1f}",
        "" if cover is None else str(cover),
    ])
    return row


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
               zero_label: str = "pedestal",
               cfg=None):
    """Scatter of log2(mean - pedestal) vs local time for one night's
    rows (as produced by measure() or read from brightness.csv).

    When temperature/humidity data are present (box_temp_c, box_rh_pct),
    renders a 2-panel chart: sky brightness on top, enclosure environment
    on the bottom, sharing a single Europe/London time axis.

    When camera.json carries sky_mag calibration and zero_label is 'black level',
    adds a secondary right-hand y-axis in mag/arcsec².

    When cover status is present (or a cover-log is discoverable), highlights
    closed-cover intervals (transparent cover during rain) in both panels and
    differentiates open vs closed frames in the scatter plot.
    """
    def _val(r, idx, key):
        if isinstance(r, dict):
            v = r.get(key)
        elif len(r) > idx:
            v = r[idx]
        else:
            v = None
        return v if v not in (None, "") else None

    times = []
    means = []
    covers = []
    box_temps = []
    box_rhs = []
    sens_temps = []
    for r in rows:
        iso = _val(r, 1, "iso_utc")
        if not iso:
            continue
        try:
            t = datetime.fromisoformat(iso).astimezone(LONDON)
        except (ValueError, TypeError):
            continue
        m = _val(r, 3, "mean")
        if m is None:
            continue
        times.append(t)
        means.append(float(m))
        cov = _val(r, 12, "cover")
        covers.append(cov if cov else "open")
        bt = _val(r, 9, "box_temp_c")
        box_temps.append(float(bt) if bt is not None else np.nan)
        rh = _val(r, 10, "box_rh_pct")
        box_rhs.append(float(rh) if rh is not None else np.nan)
        st = _val(r, 11, "senstemp_c")
        sens_temps.append(float(st) if st is not None else np.nan)

    if not times:
        return

    vals = np.array(means)
    vals, _was_msb = lsb_align(vals, pedestal)
    if pedestal is None:
        pedestal = float(np.percentile(vals, 1))
    pedestal = float(pedestal)
    signal = np.maximum(vals - pedestal, 0.5)

    has_temp = any(not np.isnan(v) for v in box_temps)
    has_rh = any(not np.isnan(v) for v in box_rhs)
    has_env = has_temp or has_rh

    # Try loading CameraConfig if not passed
    if cfg is None:
        try:
            from astro.config import CameraConfig
            cfg = CameraConfig.load(camera)
        except Exception:
            cfg = None

    # Cover status: find physical move intervals (from cover-log.csv or per-frame cover)
    closed_intervals = []
    cover_log_candidates = [
        out_path.parent / "cover-log.csv",
        Path(f"/var/lib/{camera}/cover-log.csv"),
    ]
    for cl_path in cover_log_candidates:
        if cl_path.exists():
            try:
                cur_start = None
                with open(cl_path, newline="") as f:
                    for cl_row in csv.DictReader(f):
                        if cl_row.get("event") != "move":
                            continue
                        t_u = datetime.fromisoformat(cl_row["utc"].replace("Z", "+00:00"))
                        t_l = t_u.astimezone(LONDON)
                        pos = cl_row.get("position")
                        if pos == "closed" and cur_start is None:
                            cur_start = t_l
                        elif pos == "open" and cur_start is not None:
                            closed_intervals.append((cur_start, t_l))
                            cur_start = None
                break
            except Exception:
                pass

    if not closed_intervals and any(c in ("closed", "moving") for c in covers):
        cur_start = None
        for t, c in zip(times, covers):
            if c in ("closed", "moving") and cur_start is None:
                cur_start = t
            elif c not in ("closed", "moving") and cur_start is not None:
                closed_intervals.append((cur_start, t))
                cur_start = None
        if cur_start is not None and times:
            closed_intervals.append((cur_start, times[-1]))

    # Setup figure
    if has_env:
        fig, (ax_sky, ax_env) = plt.subplots(
            2, 1, figsize=(10, 5.8), sharex=True,
            gridspec_kw={"height_ratios": [2.3, 1.1], "hspace": 0.08}
        )
    else:
        fig, ax_sky = plt.subplots(figsize=(10, 4.5))
        ax_env = None

    open_mask = np.array([c == "open" for c in covers])
    closed_mask = np.array([c == "closed" for c in covers])
    moving_mask = np.array([c == "moving" for c in covers])

    if np.any(open_mask):
        ax_sky.scatter(np.array(times)[open_mask], signal[open_mask],
                       s=4, linewidths=0, color="#007AFF", label="open", zorder=3)
    if np.any(closed_mask):
        ax_sky.scatter(np.array(times)[closed_mask], signal[closed_mask],
                       s=5, linewidths=0, color="#FF9500", label="cover closed", zorder=4)
    if np.any(moving_mask):
        ax_sky.scatter(np.array(times)[moving_mask], signal[moving_mask],
                       s=6, linewidths=0, color="#FF3B30", label="cover moving", zorder=5)

    ax_sky.set_yscale("log", base=2)
    ax_sky.yaxis.set_major_formatter(FuncFormatter(
        lambda y, _pos: f"{math.log2(y):.0f}" if y > 0 else ""))
    ax_sky.set_ylabel(f"stops above {zero_label} ({pedestal:.0f})")
    title_suffix = " & environment" if has_env else ""
    ax_sky.set_title(f"{camera} — night {night} — per-frame brightness{title_suffix}")
    ax_sky.grid(True, alpha=0.25, linestyle=":")

    # Secondary right Y-axis for mag/arcsec²
    sm = cfg.get("sky_mag") if cfg is not None else None
    if sm and zero_label == "black level":
        try:
            m0 = float(sm["mag"])
            s0 = float(sm["at_stops"])
            k = float(sm["mag_per_stop"])
            sec = ax_sky.secondary_yaxis(
                "right",
                functions=(lambda y: m0 - k * (np.log2(np.clip(y, 1e-9, None)) - s0),
                           lambda m: np.power(2.0, s0 + (m0 - np.asarray(m)) / k)))
            sec.yaxis.set_major_locator(MultipleLocator(0.5))
            sec.yaxis.set_minor_locator(NullLocator())
            sec.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
            sec.set_ylabel(f"mag/arcsec\u00b2 ({sm.get('band', '')})")
        except Exception:
            pass

    # Shading for closed cover intervals
    for s_start, s_end in closed_intervals:
        ax_sky.axvspan(s_start, s_end, color="#FF9500", alpha=0.12, zorder=1)
        if ax_env is not None:
            ax_env.axvspan(s_start, s_end, color="#FF9500", alpha=0.12, zorder=1)

    # Stacked window bounds
    if stacked_window_utc:
        try:
            t_lo = datetime.fromisoformat(stacked_window_utc[0]).astimezone(LONDON)
            t_hi = datetime.fromisoformat(stacked_window_utc[1]).astimezone(LONDON)
            for t in (t_lo, t_hi):
                ax_sky.axvline(t, color="#FF9500", linestyle="--",
                               linewidth=1.2, alpha=0.7, zorder=2)
        except (ValueError, TypeError):
            pass

    # Legend on sky plot
    legend_elements = []
    if np.any(open_mask):
        legend_elements.append(Line2D([0], [0], marker='o', color='w',
                                      markerfacecolor='#007AFF', markersize=6,
                                      label=f'open ({open_mask.sum()})'))
    if np.any(closed_mask):
        legend_elements.append(Line2D([0], [0], marker='o', color='w',
                                      markerfacecolor='#FF9500', markersize=6,
                                      label=f'closed ({closed_mask.sum()})'))
    if stacked_window_utc:
        legend_elements.append(Line2D([0], [0], color='#FF9500', linestyle='--',
                                      linewidth=1.2, label='stacked window'))
    if closed_intervals:
        legend_elements.append(Patch(facecolor='#FF9500', alpha=0.25, label='cover closed'))

    if legend_elements:
        ax_sky.legend(handles=legend_elements, loc="upper right", framealpha=0.9, fontsize=8)

    # Bottom panel (environment)
    if ax_env is not None:
        times_arr = []
        box_temps_arr = []
        box_rhs_arr = []
        sens_temps_arr = []
        for i, t in enumerate(times):
            if i > 0 and (t - times[i-1]).total_seconds() > 180:
                times_arr.append(times[i-1] + timedelta(seconds=1))
                box_temps_arr.append(np.nan)
                box_rhs_arr.append(np.nan)
                sens_temps_arr.append(np.nan)
            times_arr.append(t)
            box_temps_arr.append(box_temps[i])
            box_rhs_arr.append(box_rhs[i])
            sens_temps_arr.append(sens_temps[i])

        l_temp, = ax_env.plot(times_arr, box_temps_arr, color="#FF3B30",
                              linewidth=1.4, label="box temp (°C)")
        env_handles = [l_temp]

        has_sens = any(not np.isnan(v) for v in sens_temps)
        if has_sens:
            l_sens, = ax_env.plot(times_arr, sens_temps_arr, color="#AF52DE",
                                  linewidth=1.0, linestyle=":", alpha=0.8,
                                  label="sensor temp (°C)")
            env_handles.append(l_sens)

        ax_env.set_ylabel("temp (°C)", color="#D70015")
        ax_env.tick_params(axis="y", labelcolor="#D70015")
        ax_env.grid(True, alpha=0.25, linestyle=":")

        ax_rh = ax_env.twinx()
        l_rh, = ax_rh.plot(times_arr, box_rhs_arr, color="#34C759",
                           linewidth=1.4, label="relative humidity (%)")
        ax_rh.set_ylabel("humidity (% RH)", color="#248A3D")
        ax_rh.tick_params(axis="y", labelcolor="#248A3D")
        ax_rh.set_ylim(40, 100)
        env_handles.append(l_rh)

        ax_env.legend(handles=env_handles, loc="upper right", framealpha=0.9, fontsize=8)

    # X-axis limits and labels
    bottom_ax = ax_env if ax_env is not None else ax_sky
    night_date = datetime.strptime(night, "%Y-%m-%d").date()
    tz_label = datetime.combine(night_date, time(22, 0), tzinfo=LONDON).tzname()
    bottom_ax.set_xlabel(f"local time ({tz_label})")

    first, last = min(times), max(times)
    start = first.replace(minute=0, second=0, microsecond=0)
    floor_last = last.replace(minute=0, second=0, microsecond=0)
    end = floor_last + timedelta(hours=1) if floor_last < last else last
    bottom_ax.set_xlim(start, end)
    bottom_ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=LONDON))

    fig.autofmt_xdate()
    if not has_env and sm is None:
        fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, facecolor="white", bbox_inches="tight")
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
