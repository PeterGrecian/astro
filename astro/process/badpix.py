"""Bad-pixel (hot/cold) masking from a night's min/max stacks.

Extracted from astrocam/nightly.py. Camera-agnostic: works on any
single-plane Bayer or mono stack.

Hot:  MIN over the night > sky_median + HOT_SIGMA  -> persistently bright
      (sensor defects, stable light sources). Real stars transit fast
      enough that they don't contribute to the minimum.
Cold: MAX over the night < sky_median - COLD_SIGMA -> persistently dark
      (dust spots, dead pixels).

Sky model is median + MAD of the min image — robust against the bad
pixels themselves contaminating the statistics.
"""
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

HOT_SIGMA = 10.0
COLD_SIGMA = 10.0

# Committed master hot-pixel masks live next to each camera's config as
# <camera>/hot-master.json (the per-night badpixel.fits is post-hoc, so it is
# NOT available at capture / pipeline step 0 — the master is). See
# design/hot-pixel-mask.md.
_CONFIG_ROOT = Path(__file__).resolve().parents[2]  # repo root (astro/)


def compute_bad_pixel_mask(min_img, max_img,
                           hot_sigma=HOT_SIGMA, cold_sigma=COLD_SIGMA):
    """Returns (hot, cold, sky_med, sky_sigma, hot_thr, cold_thr)."""
    flat = min_img.ravel()
    sky_med = float(np.median(flat))
    mad = float(np.median(np.abs(flat - sky_med)))
    sky_sigma = mad * 1.4826  # MAD-to-sigma for Gaussian
    hot_thr = sky_med + hot_sigma * sky_sigma
    cold_thr = sky_med - cold_sigma * sky_sigma
    hot = min_img > hot_thr
    cold = max_img < cold_thr
    return hot, cold, sky_med, sky_sigma, hot_thr, cold_thr


def single_channel_hot(mosaic, excess=300.0, bg_excess=300.0):
    """Detect hot pixels as single-photosite spikes on the RAW BAYER MOSAIC.

    A real star is coherent across all Bayer channels; a hot pixel is a lone
    spike in ONE channel, far above its SAME-COLOUR neighbours (Bayer 2-step).
    Detecting here — BEFORE demosaic — is clean: each hot pixel is one bright
    photosite. After demosaic they bloom into shape artefacts (green→diagonal,
    R/B→L/plus, the "tiny tetris") that are hard to separate from real
    features, so mask on the mosaic and the bloom never happens.

    `mosaic` is a 2D raw Bayer frame (or a per-pixel median/mean of several
    dark frames — hot pixels persist). Returns a bool mask (True = hot).
    Complements compute_bad_pixel_mask()'s min-over-night method; OR them.
    """
    a = mosaic.astype(np.float32)
    # max over the 8 same-colour neighbours (Bayer period = 2 px)
    nbr = np.zeros_like(a)
    for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2),
                   (-2, -2), (2, 2), (-2, 2), (2, -2)):
        nbr = np.maximum(nbr, np.roll(np.roll(a, dy, 0), dx, 1))
    bg = float(np.median(a))
    return (a - nbr > excess) & (a - bg > bg_excess)


def write_bad_mask(hot, cold, sky_med, sky_sigma, hot_thr, cold_thr,
                   n_frames, path):
    """Write a uint8 image where 0 = good, 1 = hot, 2 = cold."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = np.zeros_like(hot, dtype=np.uint8)
    mask[hot] = 1
    mask[cold] = 2
    hdu = fits.ImageHDU(data=mask)
    hdu.header["SKY_MED"] = sky_med
    hdu.header["SKY_SIG"] = sky_sigma
    hdu.header["HOT_THR"] = hot_thr
    hdu.header["COLD_THR"] = cold_thr
    hdu.header["N_FRAMES"] = n_frames
    hdu.header["N_HOT"] = int(hot.sum())
    hdu.header["N_COLD"] = int(cold.sum())
    hdu.header["BAD_PCT"] = 100.0 * float(hot.sum() + cold.sum()) / hot.size
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path, overwrite=True)


def load_bad_mask(path):
    """Read a bad-mask FITS back as a bool array (True = bad)."""
    with fits.open(path) as hdul:
        return hdul[1].data != 0


def load_master(camera, raw_shape=None):
    """Load a camera's committed master hot-pixel mask as a bool array.

    Returns True = hot. The JSON stores hot pixels at BINNED resolution
    (half the raw mosaic); pass ``raw_shape=(H, W)`` to get it upsampled ×2
    to the raw mosaic grid (and trimmed/padded to exactly that shape). With
    no ``raw_shape`` the binned-resolution mask is returned.

    Apply this at STEP 0 of any PSF / detection / streak work — the per-night
    badpixel.fits is generated post-hoc and is unavailable at capture time.
    Returns None (with no error) if the camera has no master mask yet.
    """
    path = _CONFIG_ROOT / camera / "hot-master.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    h, w = doc["resolution"]
    mask = np.zeros((h, w), dtype=bool)
    yx = np.asarray(doc["hot_yx"], dtype=int)
    if len(yx):
        mask[yx[:, 0], yx[:, 1]] = True
    if raw_shape is None:
        return mask
    up = np.repeat(np.repeat(mask, 2, axis=0), 2, axis=1)
    H, W = raw_shape
    out = np.zeros((H, W), dtype=bool)
    out[: min(H, up.shape[0]), : min(W, up.shape[1])] = \
        up[: min(H, up.shape[0]), : min(W, up.shape[1])]
    return out


def apply_master(frame, camera, fill="median"):
    """Return a copy of ``frame`` with the camera's master-hot pixels filled.

    ``fill``: "median" (global frame median — good for detection/PSF; neutral),
    "zero", or a float. No-op copy if the camera has no master mask. ``frame``
    is a raw 2D mosaic; the mask is upsampled to its shape automatically.
    """
    mask = load_master(camera, raw_shape=frame.shape)
    out = frame.copy()
    if mask is None or not mask.any():
        return out
    if fill == "median":
        val = float(np.median(frame))
    elif fill == "zero":
        val = 0.0
    else:
        val = float(fill)
    out[mask] = val
    return out
