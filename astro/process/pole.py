"""Celestial-pole fitting from star tracks.

Extracted from astrocam/derot.py. Camera-agnostic: works in any pixel
frame; the caller supplies detections grouped by tile.
"""
import numpy as np

# Maximum apparent star motion between adjacent candidate epochs at a
# ~10 s co-add cadence and the worst-case off-pole tile. Used for the
# nearest-neighbour association radius in build_tracks().
ASSOC_RADIUS_PX = 30.0

# Minimum number of epochs in which a track must appear to be used in the
# pole fit. <3 underdetermines the circle.
TRACK_MIN_EPOCHS = 3


def build_tracks(detections, assoc_radius_px=ASSOC_RADIUS_PX):
    """Associate detections across frames into per-star tracks via
    greedy nearest-neighbour within assoc_radius_px.

    detections: list of (t, x, y, flux, frame_idx) sorted by t.
    Returns: list of tracks, each a list of (t, x, y, flux) in time order.

    TODO: greedy NN works near the pole where motion is sub-pixel, but at
    the field edge real stars move ~5px/epoch — same order as the
    inter-star spacing in dense regions. A proper solution uses the
    pole-prior to constrain the motion direction.
    """
    detections = sorted(detections, key=lambda d: d[0])
    tracks = []
    open_tracks = []  # list of [(t,x,y,flux), ...]; last entry is "head"
    for det in detections:
        t, x, y, flux, _ = det
        best = None
        best_d2 = assoc_radius_px ** 2
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
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    rms = float(np.sqrt(np.mean((d - r) ** 2)))
    return float(cx), float(cy), r, rms


def fit_global_pole(by_tile, track_min_epochs=TRACK_MIN_EPOCHS,
                    assoc_radius_px=ASSOC_RADIUS_PX):
    """Single global pole fit: every track (across every tile) shares a
    common rotation centre (px, py) but has its own radius. Solve by
    linear LSQ in (px, py, r_k² - px² - py²) over all detections.

    Per-tile-independent fits were severely underconstrained and produced
    one fake pole per tile (each at its own LSQ minimum). The real
    celestial pole projects to ONE point in the image, modulo lens
    distortion which is smooth and much smaller than the per-tile scatter.

    Returns (px, py, rms_px, n_tracks_used, tile_track_counts) or None if
    the system is underdetermined.
    """
    all_tracks = []
    tile_counts = {}
    for tile, dets in by_tile.items():
        tracks = build_tracks(dets, assoc_radius_px=assoc_radius_px)
        useable = [tr for tr in tracks if len(tr) >= track_min_epochs]
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
