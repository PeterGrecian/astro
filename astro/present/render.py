"""Stretch and render science images to JPEG for the web.

Extracted from astrocam/nightly.py (render_max_jpeg). Camera-agnostic.
"""
import numpy as np
from PIL import Image

# Percentiles used to clip before asinh.
JPEG_LO_PCT = 25.0
JPEG_HI_PCT = 99.9
JPEG_ASINH = 20.0


def render_asinh_jpeg(img, dst_path, lo_pct=JPEG_LO_PCT, hi_pct=JPEG_HI_PCT,
                      asinh=JPEG_ASINH, quality=88, ignore_zero=False):
    """Asinh-stretched grayscale JPEG. Returns (lo, hi) clip values.

    ignore_zero: compute the stretch percentiles over non-zero pixels
    only — for derot/mosaic images where masked tiles are exactly 0 and
    would otherwise drag the lo percentile to the floor."""
    f = img.astype(np.float32)
    sample = f[f != 0] if ignore_zero else f
    if sample.size == 0:
        sample = f
    lo = float(np.percentile(sample, lo_pct))
    hi = float(np.percentile(sample, hi_pct))
    if hi <= lo:
        hi = lo + 1.0
    s = np.clip((f - lo) / (hi - lo), 0, 1)
    s = np.arcsinh(s * asinh) / np.arcsinh(asinh)
    u8 = (s * 255).astype(np.uint8)
    Image.fromarray(u8).save(dst_path, quality=quality)
    return lo, hi
