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
import numpy as np
from astropy.io import fits

HOT_SIGMA = 10.0
COLD_SIGMA = 10.0


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
