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

import cv2
import numpy as np
from astropy.io import fits

import os

HOME = Path.home()
HERE = Path(__file__).resolve().parent
# On astrocam this is the NFS-mounted writable path; on pip it's the
# read-only mount under /mnt/puppy. Override with ASTROCAM_FRAMES.
FRAMES = Path(os.environ.get("ASTROCAM_FRAMES", str(HOME / "astrocam-frames")))
OCCLUSION_FILE = HERE / "occlusion.json"

WINDOW_S = 20 * 60        # 20 min derot window
STEP_S = 5 * 60           # 5 min between derot outputs (not enforced here;
                          # the invoker is responsible for cadence)

# Sidereal rotation rate in radians/second.
# 360 deg / 86164.0905 s (sidereal day) -> rad/s
SIDEREAL_OMEGA = 2 * np.pi / 86164.0905

# Per-tile warp margin: stars near tile edges rotate across boundaries over
# the 20-min window. Worst case: ~5 deg sky travel * sin(field_radius). For
# our 53 deg FOV and ~0.02 deg/px, 60 px covers any tile in the field.
TILE_MARGIN_PX = 60

# Maximum apparent star motion between adjacent candidate epochs at our
# co-add cadence (~10 s) and the worst-case off-pole tile. Used for the
# nearest-neighbour association radius in build_tracks().
ASSOC_RADIUS_PX = 30.0

# Minimum number of epochs in which a track must appear to be used in the
# per-tile pole fit. <3 underdetermines the circle.
TRACK_MIN_EPOCHS = 3

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
            # New layout: cands JSONs under HH/cands/. Fall through to
            # the old (HH/*.cands.json) layout for data captured before
            # the relocation.
            cands_subdir = hour_dir / "cands"
            if cands_subdir.is_dir():
                cands_paths = sorted(cands_subdir.glob("*.json"))
            else:
                cands_paths = sorted(hour_dir.glob("*.cands.json"))
            for cands_path in cands_paths:
                try:
                    meta = json.loads(cands_path.read_text())
                    t = datetime.fromisoformat(meta["utc"])
                except (OSError, KeyError, ValueError):
                    continue
                if start_utc <= t <= end_utc:
                    # FITS lives in HH/ regardless of layout — derive
                    # the basename from the cands filename.
                    base = cands_path.stem
                    # Old layout stem still carries ".cands"; strip it
                    if base.endswith(".cands"):
                        base = base[:-len(".cands")]
                    fits_path = hour_dir / f"{base}.fits.fz"
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


def fit_global_pole(by_tile):
    """Single global pole fit: every track (across every tile) shares a
    common rotation centre (px, py) but has its own radius. Solve by
    linear LSQ in (px, py, r_k² - px² - py²) over all detections.

    Per-tile-independent fits were severely underconstrained and produced
    one fake pole per tile (each at its own LSQ minimum). The real
    celestial pole projects to ONE point in the image, modulo lens
    distortion which is smooth and much smaller than the per-tile scatter.

    Returns (px, py, rms_px, n_tracks_used, tile_track_counts):
      px, py    : global pole in full-res Bayer coords
      rms_px    : RMS distance from each detection to its fitted circle
      n_tracks  : total tracks contributing
      tile_track_counts : dict tile -> n_tracks for diagnostics
    or None if the system is underdetermined.
    """
    # Build tracks per tile, then flatten into one global list, remembering
    # which tile each track came from for diagnostics.
    all_tracks = []
    tile_counts = {}
    for tile, dets in by_tile.items():
        tracks = build_tracks(dets)
        useable = [tr for tr in tracks if len(tr) >= TRACK_MIN_EPOCHS]
        tile_counts[tile] = len(useable)
        for tr in useable:
            all_tracks.append((tile, tr))
    if not all_tracks:
        return None

    n_tracks = len(all_tracks)
    n_total_pts = sum(len(tr) for _, tr in all_tracks)
    # Unknowns: px, py, plus one per-track ck = r_k² - px² - py².
    if n_total_pts < 2 + n_tracks + 1:
        return None

    rows = []
    rhs = []
    for k, (_, tr) in enumerate(all_tracks):
        for (_, x, y, _) in tr:
            row = np.zeros(2 + n_tracks)
            row[0] = 2 * x
            row[1] = 2 * y
            row[2 + k] = 1.0
            rows.append(row)
            rhs.append(x * x + y * y)
    A = np.array(rows)
    b = np.array(rhs)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    px, py = float(sol[0]), float(sol[1])
    ck = sol[2:]

    sq_res = []
    for k, (_, tr) in enumerate(all_tracks):
        r2 = ck[k] + px * px + py * py
        if r2 <= 0:
            continue
        r = np.sqrt(r2)
        for (_, x, y, _) in tr:
            d = np.sqrt((x - px) ** 2 + (y - py) ** 2)
            sq_res.append((d - r) ** 2)
    if not sq_res:
        return None
    rms = float(np.sqrt(np.mean(sq_res)))
    return px, py, rms, n_tracks, tile_counts


def _tile_bounds(c, r, n_cols, n_rows, W, H):
    """Return (x0, x1, y0, y1) tile bounds in full-res pixel coords."""
    tw = W / n_cols
    th = H / n_rows
    return (int(round(c * tw)), int(round((c + 1) * tw)),
            int(round(r * th)), int(round((r + 1) * th)))


def _padded_bounds(x0, x1, y0, y1, margin, W, H):
    """Tile bounds expanded by margin, clipped to image."""
    return (max(0, x0 - margin), min(W, x1 + margin),
            max(0, y0 - margin), min(H, y1 + margin))


def _rotation_matrix(pole_x, pole_y, angle_rad):
    """2x3 affine for rotation by `angle_rad` around (pole_x, pole_y).
    Used with cv2.warpAffine(..., WARP_INVERSE_MAP) so cv2 interprets M
    as the dst->src mapping: src_pixel = M @ [dst_x, dst_y, 1]. Inputs
    src and dst are assumed to share the same coordinate frame (i.e.
    src is NOT pre-cropped relative to the pole). If you crop the
    source to a padded tile, also translate the pole into that frame
    before calling.
    """
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    # Rotation around (px, py): x' = c(x-px) - s(y-py) + px etc.
    M = np.array([
        [c, -s, (1 - c) * pole_x + s * pole_y],
        [s,  c, -s * pole_x + (1 - c) * pole_y],
    ], dtype=np.float32)
    return M


def _load_bayer(fits_path, badmask):
    """Load Bayer co-add, apply bad-pixel mask if provided (NaN where bad)."""
    with fits.open(fits_path) as hdul:
        data = hdul[1].data.astype(np.float32)
    if badmask is not None:
        data = data.copy()
        # NaN propagates through cv2.warpAffine with INTER_LINEAR (correctly:
        # NaN windows -> NaN output). The weight pass uses a 1.0/0.0 mask so
        # bad pixels stop contributing to the weighted mean.
        data[badmask] = np.nan
    return data


def derot_stack(window, global_pole, occ, badmask=None):
    """Derotate and stack the FITS frames in `window` around a single
    global pole. Streaming: loads one frame at a time, accumulates into
    per-tile accumulators. Memory footprint ~ n_tiles * tile_size + one
    frame, NOT n_frames * frame_size.

    global_pole: (px, py) in full-res Bayer coords.
    badmask: optional bool array of shape (H, W). True = bad pixel.
      Bad pixels are set to NaN before warping so they don't contribute
      to the weighted mean.

    Returns (image, n_frames_stacked, n_tiles_used).
    """
    if not window:
        return None
    t_ref = (window[0][2].timestamp() + window[-1][2].timestamp()) / 2.0
    px, py = global_pole

    # Probe one frame for shape.
    first_path = None
    for _, fp, _, _ in window:
        if fp.exists():
            first_path = fp
            break
    if first_path is None:
        return None
    with fits.open(first_path) as hdul:
        H, W = hdul[1].shape

    n_cols = occ["cols"]
    n_rows = occ["rows"]
    trees = occ["trees"]
    col_labels = occ["col_labels"]
    row_labels = occ["row_labels"]

    # Pre-compute tile geometry and allocate per-tile accumulators.
    tile_geom = []  # list of (label, x0, x1, y0, y1, px0, px1, py0, py1, pw, ph, cpx, cpy)
    tile_img = {}
    tile_wt = {}
    for c in range(n_cols):
        for r in range(n_rows):
            label = f"{col_labels[c]}{row_labels[r]}"
            if label in trees:
                continue
            x0, x1, y0, y1 = _tile_bounds(c, r, n_cols, n_rows, W, H)
            px0, px1, py0, py1 = _padded_bounds(
                x0, x1, y0, y1, TILE_MARGIN_PX, W, H)
            pw, ph = px1 - px0, py1 - py0
            cpx, cpy = px - px0, py - py0
            tile_geom.append((label, x0, x1, y0, y1,
                              px0, px1, py0, py1, pw, ph, cpx, cpy))
            tile_img[label] = np.zeros((ph, pw), dtype=np.float32)
            tile_wt[label] = np.zeros((ph, pw), dtype=np.float32)

    # Determine rotation sign from a small sample of frames (don't need 1000s
    # for sign disambiguation; 5 well-spaced frames are plenty).
    sign = _determine_rotation_sign_streaming(
        window, px, py, occ, t_ref, W, H, badmask)

    n_loaded = 0
    for _, fits_path, t, _ in window:
        if not fits_path.exists():
            continue
        data = _load_bayer(fits_path, badmask)
        ts = t.timestamp()
        dtheta = sign * SIDEREAL_OMEGA * (t_ref - ts)
        for (label, x0, x1, y0, y1,
             p_x0, p_x1, p_y0, p_y1, pw, ph, cpx, cpy) in tile_geom:
            M = _rotation_matrix(cpx, cpy, dtheta)
            src = data[p_y0:p_y1, p_x0:p_x1]
            # For weight, use a finite-pixel mask: 1 where finite, 0 elsewhere.
            valid = np.isfinite(src).astype(np.float32)
            # Replace NaN with 0 for the image warp (cv2.warpAffine misbehaves
            # with NaN — propagation depends on neighbouring pixels via
            # bilinear interp). Multiply by the valid-mask after warping so
            # blank pixels stay properly weighted-zero.
            src_clean = np.nan_to_num(src, nan=0.0)
            warped = cv2.warpAffine(
                src_clean, M, (pw, ph),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
            w_mask = cv2.warpAffine(
                valid, M, (pw, ph),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
            tile_img[label] += warped
            tile_wt[label] += w_mask
        n_loaded += 1
        if n_loaded % 100 == 0:
            print(f"  derot: {n_loaded} frames", flush=True)
        del data

    # Assemble per-tile accumulators into the full-resolution image.
    img_accum = np.zeros((H, W), dtype=np.float32)
    wt_accum = np.zeros((H, W), dtype=np.float32)
    for (label, x0, x1, y0, y1,
         p_x0, p_x1, p_y0, p_y1, pw, ph, cpx, cpy) in tile_geom:
        cx0 = x0 - p_x0
        cy0 = y0 - p_y0
        tw = x1 - x0
        th = y1 - y0
        img_accum[y0:y1, x0:x1] += tile_img[label][cy0:cy0+th, cx0:cx0+tw]
        wt_accum[y0:y1, x0:x1] += tile_wt[label][cy0:cy0+th, cx0:cx0+tw]

    out = np.zeros_like(img_accum)
    nz = wt_accum > 0
    out[nz] = img_accum[nz] / wt_accum[nz]
    return out, n_loaded, len(tile_geom)


def _determine_rotation_sign_streaming(window, px, py, occ, t_ref, W, H,
                                       badmask, n_sample=5):
    """Pick rotation sign from a small sample of frames spanning the
    window. Stack the highest-variance tile under both signs; the
    correct sign yields higher variance (sharp stars beat smeared)."""
    if len(window) <= n_sample:
        sample = window
    else:
        step = len(window) // n_sample
        sample = [window[i] for i in range(0, len(window), step)][:n_sample]
    # Load just these frames.
    frames = []
    for _, fp, t, _ in sample:
        if not fp.exists():
            continue
        frames.append((t.timestamp(), _load_bayer(fp, badmask)))
    if not frames:
        return +1.0

    n_cols, n_rows = occ["cols"], occ["rows"]
    trees = occ["trees"]
    col_labels = occ["col_labels"]
    row_labels = occ["row_labels"]
    mid = frames[len(frames) // 2][1]
    best = None
    best_var = -1.0
    for c in range(n_cols):
        for r in range(n_rows):
            label = f"{col_labels[c]}{row_labels[r]}"
            if label in trees:
                continue
            x0, x1, y0, y1 = _tile_bounds(c, r, n_cols, n_rows, W, H)
            v = float(np.nanvar(mid[y0:y1, x0:x1]))
            if v > best_var:
                best_var = v
                best = (c, r, x0, x1, y0, y1)
    if best is None:
        return +1.0
    c, r, x0, x1, y0, y1 = best
    tw, th = x1 - x0, y1 - y0
    cpx, cpy = px - x0, py - y0
    scores = {}
    for sg in (+1.0, -1.0):
        acc = np.zeros((th, tw), dtype=np.float32)
        wt = np.zeros((th, tw), dtype=np.float32)
        for (ts, data) in frames:
            dtheta = sg * SIDEREAL_OMEGA * (t_ref - ts)
            M = _rotation_matrix(cpx, cpy, dtheta)
            src = data[y0:y1, x0:x1]
            valid = np.isfinite(src).astype(np.float32)
            src_clean = np.nan_to_num(src, nan=0.0)
            w_ = cv2.warpAffine(src_clean, M, (tw, th),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
            wm = cv2.warpAffine(valid, M, (tw, th),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
            acc += w_
            wt += wm
        stack = np.zeros_like(acc)
        nz = wt > 0
        stack[nz] = acc[nz] / wt[nz]
        scores[sg] = float(stack.var())
    return max(scores, key=scores.get)


def write_derot_fits(out_path, image, window, global_pole, pole_rms,
                     n_tracks, tile_counts, n_stacked, n_tiles_used):
    """Write the stacked image plus a small per-tile track-count table."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    primary = fits.PrimaryHDU()
    img_hdu = fits.CompImageHDU(data=image.astype(np.float32),
                                compression_type="RICE_1")
    px, py = global_pole
    img_hdu.header["DATE-OBS"] = window[0][2].isoformat()
    img_hdu.header["DATE-END"] = window[-1][2].isoformat()
    img_hdu.header["NFRAMES"] = n_stacked
    img_hdu.header["NTILES"] = n_tiles_used
    img_hdu.header["WINDOW_S"] = WINDOW_S
    img_hdu.header["BAYERPAT"] = "BGGR"
    img_hdu.header["CAMERA"] = "imx219"
    img_hdu.header["DEROT"] = "v2-global"
    img_hdu.header["POLE_X"] = float(px)
    img_hdu.header["POLE_Y"] = float(py)
    # POLE_RMS may be NaN for forced poles (no fit performed). FITS headers
    # disallow NaN floats, so omit the card in that case.
    if pole_rms is not None and np.isfinite(pole_rms):
        img_hdu.header["POLE_RMS"] = float(pole_rms)
    img_hdu.header["NTRACKS"] = int(n_tracks)

    # Tile track-count diagnostics.
    tiles = list(tile_counts.keys())
    counts = [tile_counts[t] for t in tiles]
    table_hdu = fits.BinTableHDU.from_columns([
        fits.Column(name="TILE", format="3A", array=np.array(tiles)),
        fits.Column(name="N_TRACKS", format="J", array=np.array(counts)),
    ])
    table_hdu.name = "TILETRACKS"
    fits.HDUList([primary, img_hdu, table_hdu]).writeto(out_path, overwrite=True)


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
            cands_subdir = hour_dir / "cands"
            if cands_subdir.is_dir():
                files = sorted(cands_subdir.glob("*.json"), reverse=True)
            else:
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
