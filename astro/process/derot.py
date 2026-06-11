"""Streaming per-tile derotation and stacking around a fixed pole.

Extracted from astrocam/derot.py. Camera-agnostic: the occlusion grid,
pole, Bayer pattern and camera name come from the caller.

Memory footprint ~ n_tiles * tile_size + one frame, NOT
n_frames * frame_size — frames are loaded one at a time and accumulated
into per-tile accumulators.
"""
import numpy as np
import cv2
from astropy.io import fits

# Sidereal rotation rate in radians/second.
# 360 deg / 86164.0905 s (sidereal day) -> rad/s
SIDEREAL_OMEGA = 2 * np.pi / 86164.0905

# Per-tile warp margin: stars near tile edges rotate across boundaries
# over a 20-min window. Worst case: ~5 deg sky travel * sin(field_radius).
# For a 53 deg FOV at ~0.02 deg/px, 60 px covers any tile in the field.
TILE_MARGIN_PX = 60


def tile_bounds(c, r, n_cols, n_rows, W, H):
    """Return (x0, x1, y0, y1) tile bounds in full-res pixel coords."""
    tw = W / n_cols
    th = H / n_rows
    return (int(round(c * tw)), int(round((c + 1) * tw)),
            int(round(r * th)), int(round((r + 1) * th)))


def padded_bounds(x0, x1, y0, y1, margin, W, H):
    """Tile bounds expanded by margin, clipped to image."""
    return (max(0, x0 - margin), min(W, x1 + margin),
            max(0, y0 - margin), min(H, y1 + margin))


def rotation_matrix(pole_x, pole_y, angle_rad):
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


def load_bayer(fits_path, badmask, bin2=False):
    """Load Bayer co-add, apply bad-pixel mask if provided (NaN where bad).
    bin2: 2x2 sum-bin the mosaic into grey superpixels first (the badmask
    must then be in binned coordinates)."""
    with fits.open(fits_path) as hdul:
        data = hdul[1].data
    if bin2:
        from astro.process.bayer import bin2x2
        data = bin2x2(data)
    data = data.astype(np.float32)
    if badmask is not None:
        if not bin2:
            data = data.copy()
        # NaN pixels are zeroed before warping and excluded via the
        # weight pass (1.0/0.0 valid-mask) so they stop contributing
        # to the weighted mean.
        data[badmask] = np.nan
    return data


def derot_stack(window, global_pole, occ, badmask=None,
                tile_margin_px=TILE_MARGIN_PX, bin2=False):
    """Derotate and stack the FITS frames in `window` around a single
    global pole. Streaming: loads one frame at a time, accumulates into
    per-tile accumulators.

    window: list of (cands_path, fits_path, utc_datetime, meta) in time order.
    global_pole: (px, py) in the same coords as the (possibly binned)
        working frames.
    occ: occlusion dict with cols/rows/col_labels/row_labels/trees.
    badmask: optional bool array matching the working frame shape.
    bin2: 2x2 sum-bin each frame before warping (deliverables path).

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
    if bin2:
        H, W = H // 2, W // 2

    n_cols = occ["cols"]
    n_rows = occ["rows"]
    trees = occ["trees"]
    col_labels = occ["col_labels"]
    row_labels = occ["row_labels"]

    # Pre-compute tile geometry and allocate per-tile accumulators.
    tile_geom = []  # (label, x0, x1, y0, y1, px0, px1, py0, py1, pw, ph, cpx, cpy)
    tile_img = {}
    tile_wt = {}
    for c in range(n_cols):
        for r in range(n_rows):
            label = f"{col_labels[c]}{row_labels[r]}"
            if label in trees:
                continue
            x0, x1, y0, y1 = tile_bounds(c, r, n_cols, n_rows, W, H)
            px0, px1, py0, py1 = padded_bounds(
                x0, x1, y0, y1, tile_margin_px, W, H)
            pw, ph = px1 - px0, py1 - py0
            cpx, cpy = px - px0, py - py0
            tile_geom.append((label, x0, x1, y0, y1,
                              px0, px1, py0, py1, pw, ph, cpx, cpy))
            tile_img[label] = np.zeros((ph, pw), dtype=np.float32)
            tile_wt[label] = np.zeros((ph, pw), dtype=np.float32)

    # Determine rotation sign from a small sample of frames (don't need
    # 1000s for sign disambiguation; 5 well-spaced frames are plenty).
    sign = determine_rotation_sign_streaming(
        window, px, py, occ, t_ref, W, H, badmask, bin2=bin2)

    n_loaded = 0
    for _, fits_path, t, _ in window:
        if not fits_path.exists():
            continue
        data = load_bayer(fits_path, badmask, bin2=bin2)
        ts = t.timestamp()
        dtheta = sign * SIDEREAL_OMEGA * (t_ref - ts)
        for (label, x0, x1, y0, y1,
             p_x0, p_x1, p_y0, p_y1, pw, ph, cpx, cpy) in tile_geom:
            M = rotation_matrix(cpx, cpy, dtheta)
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


def determine_rotation_sign_streaming(window, px, py, occ, t_ref, W, H,
                                      badmask, n_sample=5, bin2=False):
    """Pick rotation sign from a small sample of frames spanning the
    window. Stack the highest-variance tile under both signs; the
    correct sign yields higher variance (sharp stars beat smeared)."""
    if len(window) <= n_sample:
        sample = window
    else:
        step = len(window) // n_sample
        sample = [window[i] for i in range(0, len(window), step)][:n_sample]
    frames = []
    for _, fp, t, _ in sample:
        if not fp.exists():
            continue
        frames.append((t.timestamp(), load_bayer(fp, badmask, bin2=bin2)))
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
            x0, x1, y0, y1 = tile_bounds(c, r, n_cols, n_rows, W, H)
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
            M = rotation_matrix(cpx, cpy, dtheta)
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
                     n_tracks, tile_counts, n_stacked, n_tiles_used,
                     window_s, bayerpat, camera):
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
    img_hdu.header["WINDOW_S"] = window_s
    img_hdu.header["BAYERPAT"] = bayerpat
    img_hdu.header["CAMERA"] = camera
    img_hdu.header["DEROT"] = "v2-global"
    img_hdu.header["POLE_X"] = float(px)
    img_hdu.header["POLE_Y"] = float(py)
    # POLE_RMS may be NaN for forced poles (no fit performed). FITS headers
    # disallow NaN floats, so omit the card in that case.
    if pole_rms is not None and np.isfinite(pole_rms):
        img_hdu.header["POLE_RMS"] = float(pole_rms)
    img_hdu.header["NTRACKS"] = int(n_tracks)

    tiles = list(tile_counts.keys())
    counts = [tile_counts[t] for t in tiles]
    table_hdu = fits.BinTableHDU.from_columns([
        fits.Column(name="TILE", format="3A", array=np.array(tiles)),
        fits.Column(name="N_TRACKS", format="J", array=np.array(counts)),
    ])
    table_hdu.name = "TILETRACKS"
    fits.HDUList([primary, img_hdu, table_hdu]).writeto(out_path, overwrite=True)
