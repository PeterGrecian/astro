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

import numpy as np
from astropy.io import fits

HOME = Path.home()
HERE = Path(__file__).resolve().parent
FRAMES = HOME / "astrocam-frames"
OCCLUSION_FILE = HERE / "occlusion.json"

WINDOW_S = 20 * 60        # 20 min derot window
STEP_S = 5 * 60           # 5 min between derot outputs (not enforced here;
                          # the invoker is responsible for cadence)

# Maximum apparent star motion between adjacent candidate epochs at our
# co-add cadence (~10 s) and the worst-case off-pole tile. Used for the
# nearest-neighbour association radius in build_tracks().
ASSOC_RADIUS_PX = 30.0

# Minimum number of epochs in which a track must appear to be used in the
# per-tile pole fit. <3 underdetermines the circle.
TRACK_MIN_EPOCHS = 3

# Maximum acceptable RMS residual (in pixels) of the per-tile circle fit
# for the pole to be considered "good". Beyond this we fall back to the
# prior (pole_prior_tile H6, geometrically converted).
POLE_FIT_MAX_RMS_PX = 2.0


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


def build_tracks(detections):
    """Associate detections across frames into per-star tracks via
    greedy nearest-neighbour within ASSOC_RADIUS_PX.

    detections: list of (t, x, y, flux, frame_idx) sorted by t.
    Returns: list of tracks, each a list of (t, x, y, flux) in time order.

    TODO: this is a placeholder. Greedy NN works near the pole where motion
    is sub-pixel, but at the field edge real stars move ~5px/epoch — same
    order as the inter-star spacing in dense regions. A proper solution
    uses the pole-prior to constrain the motion direction. For now this
    will work in low-density regions and fall apart in dense ones.
    """
    # Sort by time, then sweep.
    detections = sorted(detections, key=lambda d: d[0])
    tracks = []
    open_tracks = []  # list of [(t,x,y,flux), ...]; last entry is "head"
    for det in detections:
        t, x, y, flux, _ = det
        # Try to extend an existing open track.
        best = None
        best_d2 = ASSOC_RADIUS_PX ** 2
        for tr in open_tracks:
            ht, hx, hy, _ = tr[-1]
            if t == ht:  # same epoch, can't be the same star
                continue
            d2 = (x - hx) ** 2 + (y - hy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = tr
        if best is not None:
            best.append((t, x, y, flux))
        else:
            new = [(t, x, y, flux)]
            open_tracks.append(new)
            tracks.append(new)
    return tracks


def fit_circle(points):
    """Algebraic least-squares fit of a circle to ≥3 (x, y) points.
    Returns (cx, cy, r, rms_residual). Linear system per Pratt 1987:
      (x² + y²) = 2 cx · x + 2 cy · y + (r² - cx² - cy²)
    LSQ in (cx, cy, c3=r²-cx²-cy²); recover r = sqrt(c3 + cx² + cy²)."""
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    if len(xs) < 3:
        return None
    A = np.column_stack([2 * xs, 2 * ys, np.ones_like(xs)])
    b = xs ** 2 + ys ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, c3 = sol
    r2 = c3 + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = float(np.sqrt(r2))
    # Residuals: distance from each point to the fitted circle.
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    rms = float(np.sqrt(np.mean((d - r) ** 2)))
    return float(cx), float(cy), r, rms


def fit_tile_pole(tracks):
    """Per-tile pole fit: combine all tracks with ≥TRACK_MIN_EPOCHS
    detections; each contributes a circle whose centre must coincide.

    Returns (pole_x, pole_y, rms_px, n_tracks_used) in the FULL-resolution
    Bayer pixel grid, or None if the fit underdetermined.
    """
    useable = [tr for tr in tracks if len(tr) >= TRACK_MIN_EPOCHS]
    if not useable:
        return None
    # Stack all (x, y) from all tracks into one big LSQ for the common
    # centre. We solve for (cx, cy) only, leaving per-track radius free:
    #   (xi - cx)² + (yi - cy)² = ri²    for each i in track k, radius rk
    # Rearrange: 2 xi cx + 2 yi cy + ck = xi² + yi²,  ck := rk² - cx² - cy²
    # One ck per track. Number of unknowns = 2 + n_tracks, one equation per
    # detection -> well-determined if sum(len(track)) > 2 + n_tracks.
    rows = []
    rhs = []
    n_tracks = len(useable)
    n_total_pts = sum(len(t) for t in useable)
    if n_total_pts < 2 + n_tracks + 1:
        return None
    for k, tr in enumerate(useable):
        for (_, x, y, _) in tr:
            r = np.zeros(2 + n_tracks)
            r[0] = 2 * x
            r[1] = 2 * y
            r[2 + k] = 1.0
            rows.append(r)
            rhs.append(x * x + y * y)
    A = np.array(rows)
    b = np.array(rhs)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = float(sol[0]), float(sol[1])
    ck = sol[2:]
    # RMS residual: per-detection distance from the fitted circle.
    sq_res = []
    for k, tr in enumerate(useable):
        r2 = ck[k] + cx * cx + cy * cy
        if r2 <= 0:
            continue
        r = np.sqrt(r2)
        for (_, x, y, _) in tr:
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            sq_res.append((d - r) ** 2)
    if not sq_res:
        return None
    rms = float(np.sqrt(np.mean(sq_res)))
    return cx, cy, rms, n_tracks


def fit_all_tiles(by_tile):
    """Run fit_tile_pole over every tile that has detections.
    Returns dict: tile -> (cx, cy, rms, n_tracks) or None."""
    out = {}
    for tile, dets in by_tile.items():
        tracks = build_tracks(dets)
        out[tile] = fit_tile_pole(tracks)
    return out


def derot_stack(window, tile_poles, occ):
    """Derotate and stack the FITS frames in `window` around each tile's
    local pole; produce one full-resolution stacked image.

    TODO: this is the most expensive step and is left stubbed. Sketch of
    the right implementation:
      - load each frame's Bayer data once
      - for each sky tile with a good pole, compute the rotation angle
        between frame t and the window-midpoint reference, around the
        tile's local pole (in full-res Bayer coords).
      - cv2.warpAffine the tile sub-image with that rotation, sum into
        an accumulator.
      - eves/edge tiles: no rotation, just sum (they don't see stars).
      - tree tiles: zero (excluded).
    For the scaffold, just sum all frames as a sanity baseline so the
    output FITS shape and headers are right.
    """
    if not window:
        return None
    accum = None
    n = 0
    for _, fits_path, _, _ in window:
        if not fits_path.exists():
            continue
        with fits.open(fits_path) as hdul:
            data = hdul[1].data.astype(np.float32)
        if accum is None:
            accum = data
        else:
            accum += data
        n += 1
    if accum is None:
        return None
    # Keep as float for now; downstream will widen anyway.
    return accum, n


def write_derot_fits(out_path, image, window, tile_poles):
    """Write the stacked image with per-tile pole table HDU."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    primary = fits.PrimaryHDU()
    img_hdu = fits.CompImageHDU(data=image.astype(np.float32),
                                compression_type="RICE_1")
    t_start = window[0][2].isoformat()
    t_end = window[-1][2].isoformat()
    img_hdu.header["DATE-OBS"] = t_start
    img_hdu.header["DATE-END"] = t_end
    img_hdu.header["NFRAMES"] = len(window)
    img_hdu.header["WINDOW_S"] = WINDOW_S
    img_hdu.header["BAYERPAT"] = "BGGR"
    img_hdu.header["CAMERA"] = "imx219"
    img_hdu.header["DEROT"] = "scaffold"  # remove when real derot lands

    # Per-tile pole table.
    tiles, pxs, pys, rmss, n_tracks = [], [], [], [], []
    for tile, fit in tile_poles.items():
        tiles.append(tile)
        if fit is None:
            pxs.append(np.nan); pys.append(np.nan)
            rmss.append(np.nan); n_tracks.append(0)
        else:
            cx, cy, rms, n = fit
            pxs.append(cx); pys.append(cy); rmss.append(rms); n_tracks.append(n)
    pole_hdu = fits.BinTableHDU.from_columns([
        fits.Column(name="TILE", format="3A", array=np.array(tiles)),
        fits.Column(name="POLE_X", format="E", array=np.array(pxs)),
        fits.Column(name="POLE_Y", format="E", array=np.array(pys)),
        fits.Column(name="RMS_PX", format="E", array=np.array(rmss)),
        fits.Column(name="N_TRACKS", format="J", array=np.array(n_tracks)),
    ])
    pole_hdu.name = "TILEPOLES"
    fits.HDUList([primary, img_hdu, pole_hdu]).writeto(out_path, overwrite=True)


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
    end_utc = latest_finished_co_add()
    if end_utc is None:
        print("no candidate files found; nothing to do", file=sys.stderr)
        return 1
    window = scan_window(end_utc)
    if len(window) < 3:
        print(f"window too short: {len(window)} epochs", file=sys.stderr)
        return 1
    print(f"window: {window[0][2].isoformat()} .. {window[-1][2].isoformat()}  "
          f"({len(window)} epochs)")

    by_tile = candidates_by_tile(window)
    print(f"detections per tile (top): "
          f"{sorted(((t, len(v)) for t, v in by_tile.items()), key=lambda x: -x[1])[:6]}")

    tile_poles = fit_all_tiles(by_tile)
    good = [t for t, f in tile_poles.items()
            if f is not None and f[2] <= POLE_FIT_MAX_RMS_PX]
    print(f"per-tile poles fitted: {len([f for f in tile_poles.values() if f is not None])}/{len(tile_poles)} "
          f"(good: {len(good)})")

    stack = derot_stack(window, tile_poles, occ)
    if stack is None:
        print("no frames could be loaded for stacking", file=sys.stderr)
        return 1
    image, n_stacked = stack

    derot_root = FRAMES / "derot"
    out_dir = derot_root / end_utc.strftime("%Y-%m-%d") / end_utc.strftime("%H")
    out_path = out_dir / f"{end_utc.strftime('%M%S')}.fits.fz"
    write_derot_fits(out_path, image, window, tile_poles)
    print(f"wrote {out_path}  ({n_stacked} frames stacked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
