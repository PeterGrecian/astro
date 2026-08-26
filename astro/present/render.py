"""Stretch and render science images to JPEG for the web.

Extracted from astrocam/nightly.py (render_max_jpeg). Camera-agnostic.
"""
import numpy as np
from PIL import Image

# Percentiles used to clip before asinh.
JPEG_LO_PCT = 25.0
JPEG_HI_PCT = 99.9
JPEG_ASINH = 20.0


# --- Area-adjusted gain --------------------------------------------------
#
# A single global stretch has one gain for the whole frame, so the bright
# areas (house windows, the light-pollution dome low in frame) set the
# clip points and the faint stars in the dark parts of the sky are left
# in the bottom bucket. Area-adjusted gain divides the image by a smooth
# map of its own local background before the stretch: each *area* gets
# the gain it needs, so stars come up over dark sky while the windows
# stay in range instead of blowing out.
#
# The background map is a block low-percentile (not a mean) so stars and
# trails do not inflate it, upsampled bilinearly. `strength` blends
# between no correction (0.0) and full flat-field (1.0).

AREA_GAIN_BLOCKS = 24
AREA_GAIN_PCT = 30.0
# Gain is clamped: a streetlamp in one tile would otherwise drive the gain
# there near zero and punch a dark halo into the sky around it.
AREA_GAIN_MIN = 0.35
AREA_GAIN_MAX = 4.0


def local_background(img, blocks=AREA_GAIN_BLOCKS, pct=AREA_GAIN_PCT):
    """Smooth per-area background of a 2-D image, same shape as `img`.

    The frame is cut into roughly `blocks` tiles across its long axis; each
    tile contributes its `pct` percentile, and that coarse map is scaled
    back up bilinearly. Percentile, not mean, so a tile full of star trails
    still reports its sky level.
    """
    f = np.asarray(img, dtype=np.float32)
    H, W = f.shape
    step = max(8, int(round(max(H, W) / max(1, blocks))))
    ny = max(1, H // step)
    nx = max(1, W // step)
    coarse = np.empty((ny, nx), dtype=np.float32)
    ys = np.linspace(0, H, ny + 1).astype(int)
    xs = np.linspace(0, W, nx + 1).astype(int)
    for j in range(ny):
        for i in range(nx):
            tile = f[ys[j]:ys[j + 1], xs[i]:xs[i + 1]]
            coarse[j, i] = np.percentile(tile, pct) if tile.size else 0.0
    if ny < 2 or nx < 2:
        return np.full((H, W), float(coarse.mean()), dtype=np.float32)
    # Smooth the coarse grid before upsampling. Without this, one tile
    # holding a streetlamp gets a background several times its neighbours'
    # and the upsample paints a visible seam across the sky.
    coarse = _box3(coarse)
    # Bicubic upsample via PIL (no scipy dependency in the pipeline).
    bg = np.asarray(Image.fromarray(coarse, mode="F")
                    .resize((W, H), Image.BICUBIC), dtype=np.float32)
    return np.maximum(bg, 0.0)


def _box3(a):
    """3x3 box blur with edge replication, on the small coarse grid."""
    p = np.pad(a, 1, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
    return out / 9.0


def sky_mask(img, frac=0.6, blocks=AREA_GAIN_BLOCKS, pct=AREA_GAIN_PCT, bg=None):
    """Boolean mask of the `frac` darkest-background part of the frame.

    "Sky" here means low local background, not low pixel value — a star
    trail is bright but sits on sky, and we want it inside the mask. Used
    to keep the streetlamps and windows out of the stretch percentiles.
    """
    lum = np.asarray(img, dtype=np.float32)
    if lum.ndim == 3:
        lum = lum.sum(axis=-1)
    if bg is None:
        bg = local_background(lum, blocks=blocks, pct=pct)
    cut = float(np.percentile(bg, 100.0 * float(np.clip(frac, 0.01, 1.0))))
    return bg <= cut


def area_gain(img, strength=1.0, blocks=AREA_GAIN_BLOCKS, pct=AREA_GAIN_PCT,
              gain_min=AREA_GAIN_MIN, gain_max=AREA_GAIN_MAX):
    """Divide `img` by its own normalised local background.

    2-D input is corrected directly; (H, W, 3) input takes ONE gain map
    derived from luminance so colour balance is untouched. The map is
    normalised to mean 1, so overall level (and the percentiles the
    stretch then picks) stays in the same ballpark as the input.
    """
    f = np.asarray(img, dtype=np.float32)
    if strength <= 0:
        return f
    lum = f.sum(axis=-1) if f.ndim == 3 else f
    bg = local_background(lum, blocks=blocks, pct=pct)
    ref = float(np.median(bg))
    if not np.isfinite(ref) or ref <= 0:
        return f
    g = np.clip(ref / np.maximum(bg, max(ref * 1e-3, 1e-6)), gain_min, gain_max)
    if strength < 1.0:
        g = g ** float(strength)
    return f * (g[..., None] if f.ndim == 3 else g)


def render_asinh_jpeg_rgb(img, dst_path, lo_pct=JPEG_LO_PCT, hi_pct=JPEG_HI_PCT,
                          asinh=JPEG_ASINH, quality=88, rotate_180=False,
                          area_gain_strength=0.0, sky_frac=0.0):
    """Asinh-stretched RGB JPEG. img is (H, W, 3) with channel order R,G,B.
    Each channel stretched against ITS OWN percentiles — auto-WB style,
    so dawn pinks pop without manual gain ratios.

    sky_frac: take the stretch percentiles over only the `sky_frac`
    darkest-background fraction of the frame, so the streetlamps stop
    setting the ceiling and the sky gets the whole range. The lamps then
    clip to white, which is what they look like anyway. 0 disables."""
    from PIL import Image as _Image
    f = img.astype(np.float32)
    if area_gain_strength > 0:
        f = area_gain(f, strength=area_gain_strength)
    m = sky_mask(f, sky_frac) if sky_frac > 0 else None
    out = np.empty(f.shape, dtype=np.uint8)
    for ch in range(3):
        c = f[..., ch]
        samp = c[m] if m is not None and m.any() else c
        lo = float(np.percentile(samp, lo_pct))
        hi = float(np.percentile(samp, hi_pct))
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
                      rotate_180=False, area_gain_strength=0.0, sky_frac=0.0):
    """Asinh-stretched grayscale JPEG. Returns (lo, hi) clip values.

    ignore_zero: compute the stretch percentiles over non-zero pixels
    only — for derot/mosaic images where masked tiles are exactly 0 and
    would otherwise drag the lo percentile to the floor.

    sky_frac: take the stretch percentiles over only the `sky_frac`
    darkest-background fraction of the frame, so the streetlamps stop
    setting the ceiling. See render_asinh_jpeg_rgb. 0 disables."""
    f = img.astype(np.float32)
    if area_gain_strength > 0:
        f = area_gain(f, strength=area_gain_strength)
    sample = f[f != 0] if ignore_zero else f
    if sky_frac > 0:
        m = sky_mask(f, sky_frac)
        if ignore_zero:
            m = m & (f != 0)
        if m.any():
            sample = f[m]
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
