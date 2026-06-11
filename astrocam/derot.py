#!/usr/bin/env python3
"""astrocam derot stage: rolling 20-min window -> per-patch pole fit ->
tile derotation -> stacked .fits.fz delivered to puppy.

Reads:
  ~/astrocam-frames/YYYY-MM-DD/HH/MMSS.{cands.json, fits.fz}
Writes:
  ~/astrocam-frames/derot/YYYY-MM-DD/HH/MMSS.fits.fz
  (latter path is on puppy via the same NFS root.)

Invoke once per 5-min step (timer or external loop). Each run takes the
most recent finished co-add as the window-end and assembles the window
[end - WINDOW_S, end].

This is a scaffold: pole fit and stacking are stubbed with TODOs marking
the hard parts. The CLI works end-to-end (reads window, identifies
candidate stars by tile, would-be writes output path) so we can iterate
on the maths against real data without rebuilding the IO every time.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astropy.io import fits

import os

HOME = Path.home()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from astro.process.pole import fit_global_pole  # noqa: E402
from astro.process import derot as _derot  # noqa: E402
from astro.process.derot import derot_stack  # noqa: E402
# On astrocam this is the NFS-mounted writable path; on pip it's the
# read-only mount under /mnt/puppy. Override with ASTROCAM_FRAMES.
FRAMES = Path(os.environ.get("ASTROCAM_FRAMES", str(HOME / "astrocam-frames")))
OCCLUSION_FILE = HERE / "occlusion.json"

WINDOW_S = 20 * 60        # 20 min derot window
STEP_S = 5 * 60           # 5 min between derot outputs (not enforced here;
                          # the invoker is responsible for cadence)

BAYERPAT = "BGGR"
CAMERA = "imx219"

def utcnow():
    return datetime.now(timezone.utc)


def load_occlusion():
    occ = json.loads(OCCLUSION_FILE.read_text())
    cols = occ["grid"]["cols"]
    rows = occ["grid"]["rows"]
    col_labels = occ["grid"]["col_labels"]
    row_labels = occ["grid"]["row_labels"]
    trees = set(occ["trees"])
    pole_prior = occ.get("pole_prior_tile", "H6")
    sky = [(c, r, f"{col_labels[c]}{row_labels[r]}")
           for c in range(cols) for r in range(rows)
           if f"{col_labels[c]}{row_labels[r]}" not in trees]
    return {
        "cols": cols, "rows": rows, "col_labels": col_labels,
        "row_labels": row_labels, "trees": trees,
        "sky_tiles": sky, "pole_prior_tile": pole_prior,
    }


def scan_window(end_utc, window_s=WINDOW_S):
    """Return list of (cands_path, fits_path, utc) for all co-adds whose
    .cands.json utc falls in [end - window_s, end]. Searches the day dir
    of end_utc plus the previous day's last hour to handle hour/day
    boundaries cleanly."""
    start_utc = end_utc - timedelta(seconds=window_s)
    found = []
    # Walk the two day dirs that could contain the window.
    days_to_check = {start_utc.strftime("%Y-%m-%d"),
                     end_utc.strftime("%Y-%m-%d")}
    for day in days_to_check:
        day_dir = FRAMES / day
        if not day_dir.exists():
            continue
        for hour_dir in sorted(day_dir.iterdir()):
            if not hour_dir.is_dir() or not hour_dir.name.isdigit():
                continue
            for cands_path in sorted(hour_dir.glob("*.cands.json")):
                try:
                    meta = json.loads(cands_path.read_text())
                    t = datetime.fromisoformat(meta["utc"])
                except (OSError, KeyError, ValueError):
                    continue
                if start_utc <= t <= end_utc:
                    fits_path = cands_path.with_suffix("").with_suffix(".fits.fz")
                    found.append((cands_path, fits_path, t, meta))
    found.sort(key=lambda x: x[2])
    return found


def candidates_by_tile(window):
    """Group candidate detections by tile across all frames in the window.
    Returns dict: tile -> list of (t_unix, x_full, y_full, flux, frame_idx)."""
    out = defaultdict(list)
    for frame_idx, (_, _, t, meta) in enumerate(window):
        t_unix = t.timestamp()
        for s in meta["stars"]:
            out[s["tile"]].append((
                t_unix, s["x"], s["y"], s["flux"], frame_idx,
            ))
    return out


def write_derot_fits(out_path, image, window, global_pole, pole_rms,
                     n_tracks, tile_counts, n_stacked, n_tiles_used):
    _derot.write_derot_fits(out_path, image, window, global_pole, pole_rms,
                            n_tracks, tile_counts, n_stacked, n_tiles_used,
                            window_s=WINDOW_S, bayerpat=BAYERPAT,
                            camera=CAMERA)


def latest_finished_co_add():
    """Return the utc of the most recent .cands.json on disk, or None.
    Used as the default window end."""
    today = utcnow().strftime("%Y-%m-%d")
    yesterday = (utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    latest_t = None
    for day in (today, yesterday):
        day_dir = FRAMES / day
        if not day_dir.exists():
            continue
        for hour_dir in sorted(day_dir.iterdir(), reverse=True):
            if not hour_dir.is_dir() or not hour_dir.name.isdigit():
                continue
            files = sorted(hour_dir.glob("*.cands.json"), reverse=True)
            if files:
                meta = json.loads(files[0].read_text())
                latest_t = datetime.fromisoformat(meta["utc"])
                return latest_t
    return latest_t


def main(argv):
    occ = load_occlusion()
    # CLI: --window-end <iso>, --pole <x,y>, --window-s <int>,
    #      --badmask <path>  (FITS uint8: 0=good, !=0 -> masked)
    args = argv[1:]
    end_utc = None
    forced_pole = None
    window_s = WINDOW_S
    badmask_path = None
    while args:
        a = args.pop(0)
        if a == "--window-end" and args:
            v = args.pop(0)
            end_utc = datetime.fromisoformat(v)
            if end_utc.tzinfo is None:
                end_utc = end_utc.replace(tzinfo=timezone.utc)
        elif a == "--pole" and args:
            v = args.pop(0)
            forced_pole = tuple(float(s) for s in v.split(","))
            if len(forced_pole) != 2:
                print(f"--pole expects 'x,y', got '{v}'", file=sys.stderr)
                return 2
        elif a == "--window-s" and args:
            window_s = int(args.pop(0))
        elif a == "--badmask" and args:
            badmask_path = args.pop(0)
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            return 2

    badmask = None
    if badmask_path is not None:
        with fits.open(badmask_path) as hdul:
            m = hdul[1].data
        badmask = m != 0
        print(f"loaded bad mask: {badmask.sum()} pixels ({100*badmask.sum()/badmask.size:.3f}%)")
    if end_utc is None:
        end_utc = latest_finished_co_add()
    if end_utc is None:
        print("no candidate files found; nothing to do", file=sys.stderr)
        return 1
    window = scan_window(end_utc, window_s=window_s)
    if len(window) < 3:
        print(f"window too short: {len(window)} epochs", file=sys.stderr)
        return 1
    print(f"window: {window[0][2].isoformat()} .. {window[-1][2].isoformat()}  "
          f"({len(window)} epochs)")

    by_tile = candidates_by_tile(window)
    print(f"detections per tile (top): "
          f"{sorted(((t, len(v)) for t, v in by_tile.items()), key=lambda x: -x[1])[:6]}")

    if forced_pole is not None:
        px, py = forced_pole
        rms = float("nan")
        n_tracks = 0
        tile_counts = {t: 0 for t in by_tile}
        print(f"forced pole: ({px:.1f}, {py:.1f})  (no fit)")
    else:
        fit = fit_global_pole(by_tile)
        if fit is None:
            print("global pole fit failed (insufficient data)", file=sys.stderr)
            return 1
        px, py, rms, n_tracks, tile_counts = fit
        print(f"global pole: ({px:.1f}, {py:.1f})  rms={rms:.2f}px  "
              f"n_tracks={n_tracks}")

    stack = derot_stack(window, (px, py), occ, badmask=badmask)
    if stack is None:
        print("no frames could be loaded for stacking", file=sys.stderr)
        return 1
    image, n_stacked, n_tiles_used = stack

    # Co-locate the derot output next to the source co-add it ends with.
    # Filenames are MMSS.fits.fz so we split on the leading dot only.
    last_path = window[-1][1]
    mmss = last_path.name.split(".")[0]
    suffix = ".derot.masked.fits.fz" if badmask is not None else ".derot.fits.fz"
    out_path = last_path.with_name(f"{mmss}{suffix}")
    write_derot_fits(out_path, image, window,
                     global_pole=(px, py), pole_rms=rms,
                     n_tracks=n_tracks, tile_counts=tile_counts,
                     n_stacked=n_stacked, n_tiles_used=n_tiles_used)
    print(f"wrote {out_path}  ({n_stacked} frames stacked, "
          f"{n_tiles_used} tiles derotated)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
