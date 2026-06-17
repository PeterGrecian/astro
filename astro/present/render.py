"""Stretch and render science images to JPEG for the web.

Extracted from astrocam/nightly.py (render_max_jpeg). Camera-agnostic.
"""
import numpy as np
from PIL import Image

# Percentiles used to clip before asinh.
JPEG_LO_PCT = 25.0
JPEG_HI_PCT = 99.9
JPEG_ASINH = 20.0


def render_asinh_jpeg_rgb(img, dst_path, lo_pct=JPEG_LO_PCT, hi_pct=JPEG_HI_PCT,
                          asinh=JPEG_ASINH, quality=88, rotate_180=False):
    """Asinh-stretched RGB JPEG. img is (H, W, 3) with channel order R,G,B.
    Each channel stretched against ITS OWN percentiles — auto-WB style,
    so dawn pinks pop without manual gain ratios."""
    from PIL import Image as _Image
    f = img.astype(np.float32)
    out = np.empty(f.shape, dtype=np.uint8)
    for ch in range(3):
        c = f[..., ch]
        lo = float(np.percentile(c, lo_pct))
        hi = float(np.percentile(c, hi_pct))
        if hi <= lo:
            hi = lo + 1.0
        s = np.clip((c - lo) / (hi - lo), 0, 1)
        s = np.arcsinh(s * asinh) / np.arcsinh(asinh)
        out[..., ch] = (s * 255).astype(np.uint8)
    if rotate_180:
        out = np.rot90(out, 2)
    _Image.fromarray(out, mode="RGB").save(dst_path, quality=quality)


def render_signed_asinh_jpeg(img, dst_path, hi_pct=JPEG_HI_PCT,
                             asinh=JPEG_ASINH, quality=88,
                             neg_blue=False, rotate_180=False):
    """Signed-input asinh JPEG. Positives → white asinh; negatives
    either clipped (neg_blue=False, equivalent to abs/clip) or shown
    as a blue lobe (neg_blue=True, output RGB).

    Stretch is symmetric around zero so positives and negatives use
    the same magnitude scale. The hi_pct percentile of |img| sets
    the magnitude range.
    """
    f = img.astype(np.float32)
    mag = np.abs(f)
    hi = float(np.percentile(mag, hi_pct))
    if hi <= 0:
        hi = 1.0

    def stretch(x):
        s = np.clip(x / hi, 0, 1)
        return np.arcsinh(s * asinh) / np.arcsinh(asinh)

    if neg_blue:
        pos = np.where(f > 0, f, 0.0)
        neg = np.where(f < 0, -f, 0.0)
        pos_s = stretch(pos)
        neg_s = stretch(neg)
        rgb = np.empty(f.shape + (3,), dtype=np.uint8)
        # Red, green from positives only; blue is positives + negatives,
        # so positive regions stay neutral grey and negatives glow blue.
        rgb[..., 0] = (pos_s * 255).astype(np.uint8)
        rgb[..., 1] = (pos_s * 255).astype(np.uint8)
        rgb[..., 2] = (np.clip(pos_s + neg_s, 0, 1) * 255).astype(np.uint8)
        if rotate_180:
            rgb = np.rot90(rgb, 2)
        Image.fromarray(rgb, mode="RGB").save(dst_path, quality=quality)
    else:
        # No blue lobe: just clip negatives at zero and render mono.
        pos_s = stretch(np.where(f > 0, f, 0.0))
        u8 = (pos_s * 255).astype(np.uint8)
        if rotate_180:
            u8 = np.rot90(u8, 2)
        Image.fromarray(u8).save(dst_path, quality=quality)


def render_signed_asinh_jpeg_rgb(img, dst_path, hi_pct=JPEG_HI_PCT,
                                 asinh=JPEG_ASINH, quality=88,
                                 neg_blue=False, rotate_180=False):
    """Signed-input asinh RGB JPEG. img is (H, W, 3).

    With neg_blue=False: per-channel positive-clip + asinh, same as
    render_asinh_jpeg_rgb but symmetric scaling around zero per channel.

    With neg_blue=True: positives render as per-channel RGB asinh;
    where global luminance (sum of channels) went negative the output
    glows blue proportional to |Δluminance|. The "is this pixel down
    overall" decision is global so a meteor through a green-leaning
    bayer pattern doesn't show one channel as blue.
    """
    f = img.astype(np.float32)
    # Per-channel positive stretch (always rendered).
    pos = np.where(f > 0, f, 0.0)
    pos_rgb = np.empty(f.shape, dtype=np.uint8)
    for ch in range(3):
        c = pos[..., ch]
        hi = float(np.percentile(np.abs(f[..., ch]), hi_pct)) or 1.0
        s = np.clip(c / hi, 0, 1)
        s = np.arcsinh(s * asinh) / np.arcsinh(asinh)
        pos_rgb[..., ch] = (s * 255).astype(np.uint8)
    if not neg_blue:
        out = pos_rgb
    else:
        lum = f.sum(axis=-1)
        neg = np.where(lum < 0, -lum, 0.0)
        hi = float(np.percentile(np.abs(lum), hi_pct)) or 1.0
        neg_s = np.arcsinh(np.clip(neg / hi, 0, 1) * asinh) / np.arcsinh(asinh)
        out = pos_rgb.copy()
        out[..., 2] = np.clip(out[..., 2].astype(np.int32) +
                              (neg_s * 255).astype(np.int32), 0, 255).astype(np.uint8)
    if rotate_180:
        out = np.rot90(out, 2)
    Image.fromarray(out, mode="RGB").save(dst_path, quality=quality)


def render_asinh_jpeg(img, dst_path, lo_pct=JPEG_LO_PCT, hi_pct=JPEG_HI_PCT,
                      asinh=JPEG_ASINH, quality=88, ignore_zero=False,
                      rotate_180=False):
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
    if rotate_180:
        u8 = np.rot90(u8, 2)
    Image.fromarray(u8).save(dst_path, quality=quality)
    return lo, hi
