#!/usr/bin/env python3
"""astrocam nightly stack: max / min / sum + hot-pixel mask + JPEG.

Runs once at noon for the night just ended. The "night of 2026-06-09"
is the rollover window 2026-06-09 12:00 UTC -> 2026-06-10 12:00 UTC, so
the dir name covers both calendar days of an observing session.

Outputs land beside the source frames:
  ~/astrocam-frames/<NIGHT>/max.fits.fz   star-trail picture (canonical)
  ~/astrocam-frames/<NIGHT>/max.jpg       asinh-stretched JPEG (web)
  ~/astrocam-frames/<NIGHT>/min.fits.fz   per-pixel minimum (private)
  ~/astrocam-frames/<NIGHT>/sum.fits.fz   integrated light (private)
  ~/astrocam-frames/<NIGHT>/hotpixel.fits boolean mask (1 = hot)

Hot-pixel definition: pixels where MIN over the night exceeds the sky
median by >10 sigma. Real stars transit fast enough that they don't
contribute to the minimum; persistent hot/warm pixels and stable light
sources (e.g. F1 twilight glow region) do.

CLI:
  python -m astrocam.nightly                # most recently completed night
  python -m astrocam.nightly --night YYYY-MM-DD
"""
import glob
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits
from PIL import Image

HOME = Path.home()
FRAMES = Path(os.environ.get("ASTROCAM_FRAMES", str(HOME / "astrocam-frames")))

# Bad-pixel thresholds (in sky sigmas, MAD-derived):
#  - HOT:  min over night > sky_median + HOT_SIGMA  -> persistently bright
#  - COLD: max over night < sky_median - COLD_SIGMA -> persistently dark
HOT_SIGMA = 10.0
COLD_SIGMA = 10.0

# JPEG stretch: percentiles used to clip before asinh.
JPEG_LO_PCT = 25.0
JPEG_HI_PCT = 99.9
JPEG_ASINH = 20.0


def current_night_dir():
    """The night that JUST ended. If it's after noon UTC, that's today
    (since the night runs from yesterday noon to today noon). Before noon,
    last night ran from the day-before-yesterday noon to yesterday noon —
    its label is yesterday's date."""
    now = datetime.now(timezone.utc)
    if now.hour >= 12:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return (now - timedelta(days=2)).strftime("%Y-%m-%d")


def list_night_frames(night):
    """Return all co-add .fits.fz under the noon-rollover night window.

    night = 'YYYY-MM-DD' -> window [night 12:00 UTC, night+1 12:00 UTC).
    Frames are in hourly subdirs YYYY-MM-DD/HH/MMSS.fits.fz, so we
    walk both date dirs and filter to the rollover window.
    """
    start = datetime.strptime(night, "%Y-%m-%d").replace(
        hour=12, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    day_a = start.strftime("%Y-%m-%d")
    day_b = end.strftime("%Y-%m-%d")
    files = []
    for day in (day_a, day_b):
        for hour in range(24):
            pat = str(FRAMES / day / f"{hour:02d}" / "*.fits.fz")
            for f in glob.glob(pat):
                if ".derot." in f or "/max.fits" in f or "/min.fits" in f \
                        or "/sum.fits" in f:
                    continue
                files.append(Path(f))
    # Filter by DATE-OBS in the window.
    keep = []
    for f in files:
        try:
            with fits.open(f) as hdul:
                t = datetime.fromisoformat(hdul[1].header["DATE-OBS"])
        except (OSError, KeyError, ValueError):
            continue
        if start <= t < end:
            keep.append((t, f))
    keep.sort()
    return keep


def stack_night(frames):
    """One-pass min/max/sum across all night frames. Returns (max_img,
    min_img, sum_img, n)."""
    if not frames:
        return None
    with fits.open(frames[0][1]) as hdul:
        sample = hdul[1].data
    H, W = sample.shape
    # uint16 saturates at 65535 — single co-add ceiling is 8184, so plenty
    # of headroom. Sum needs float64 (974 * 8184 = ~8e6, fits in int32 too
    # but float64 keeps the math simple).
    max_img = np.zeros((H, W), dtype=np.uint16)
    min_img = np.full((H, W), 65535, dtype=np.uint16)
    sum_img = np.zeros((H, W), dtype=np.float64)
    for i, (_, f) in enumerate(frames):
        with fits.open(f) as hdul:
            d = hdul[1].data
        np.maximum(max_img, d, out=max_img)
        np.minimum(min_img, d, out=min_img)
        sum_img += d
        if i % 100 == 0:
            print(f"  {i}/{len(frames)}", flush=True)
    return max_img, min_img, sum_img, len(frames)


def compute_bad_pixel_mask(min_img, max_img):
    """Pixels persistently bright (hot) or dark (cold) across the night.
    Uses median+MAD of min_img as the sky model — robust against the bad
    pixels themselves contaminating the statistics."""
    flat = min_img.ravel()
    sky_med = float(np.median(flat))
    mad = float(np.median(np.abs(flat - sky_med)))
    sky_sigma = mad * 1.4826  # MAD-to-sigma for Gaussian
    hot_thr = sky_med + HOT_SIGMA * sky_sigma
    cold_thr = sky_med - COLD_SIGMA * sky_sigma
    hot = min_img > hot_thr
    cold = max_img < cold_thr
    return hot, cold, sky_med, sky_sigma, hot_thr, cold_thr


def render_max_jpeg(max_img, dst_path):
    """Asinh-stretched grayscale JPEG of the max image."""
    f = max_img.astype(np.float32)
    lo = float(np.percentile(f, JPEG_LO_PCT))
    hi = float(np.percentile(f, JPEG_HI_PCT))
    if hi <= lo:
        hi = lo + 1.0
    s = np.clip((f - lo) / (hi - lo), 0, 1)
    s = np.arcsinh(s * JPEG_ASINH) / np.arcsinh(JPEG_ASINH)
    u8 = (s * 255).astype(np.uint8)
    Image.fromarray(u8).save(dst_path, quality=88)
    return lo, hi


def write_fits_u16(arr, path):
    """Rice-compressed uint16 FITS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.CompImageHDU(data=arr.astype(np.uint16),
                            compression_type="RICE_1")
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path, overwrite=True)


def write_fits_f32(arr, path):
    """Rice-compressed float FITS (used for sum which exceeds uint16)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.CompImageHDU(data=arr.astype(np.float32),
                            compression_type="RICE_1")
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path, overwrite=True)


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


def main(argv):
    args = argv[1:]
    night = None
    while args:
        a = args.pop(0)
        if a == "--night" and args:
            night = args.pop(0)
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            return 2
    if night is None:
        night = current_night_dir()
    print(f"night: {night}")

    frames = list_night_frames(night)
    if not frames:
        print("no frames found for that night", file=sys.stderr)
        return 1
    print(f"frames: {len(frames)}  "
          f"first={frames[0][0].isoformat()}  last={frames[-1][0].isoformat()}")

    t0 = time.monotonic()
    max_img, min_img, sum_img, n = stack_night(frames)
    print(f"stacked in {time.monotonic()-t0:.1f}s")

    out_dir = FRAMES / night
    out_dir.mkdir(parents=True, exist_ok=True)

    write_fits_u16(max_img, out_dir / "max.fits.fz")
    write_fits_u16(min_img, out_dir / "min.fits.fz")
    write_fits_f32(sum_img, out_dir / "sum.fits.fz")

    hot, cold, sky_med, sky_sigma, hot_thr, cold_thr = compute_bad_pixel_mask(
        min_img, max_img)
    write_bad_mask(hot, cold, sky_med, sky_sigma, hot_thr, cold_thr, n,
                   out_dir / "badpixel.fits")
    print(f"hot pixels: {hot.sum()} ({100*hot.sum()/hot.size:.3f}%)  "
          f"cold pixels: {cold.sum()} ({100*cold.sum()/cold.size:.3f}%)  "
          f"sky_med={sky_med:.1f}  sky_sig={sky_sigma:.2f}  "
          f"hot>{hot_thr:.1f}  cold<{cold_thr:.1f}")

    lo, hi = render_max_jpeg(max_img, out_dir / "max.jpg")
    print(f"max.jpg stretch: lo={lo:.0f}  hi={hi:.0f}")

    print(f"wrote: {out_dir}/{{max,min,sum}}.fits.fz, badpixel.fits, max.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
