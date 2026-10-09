"""astro.psf — star width split across and along the trail: the focus metric.

A fixed camera exposes for tens of seconds, so every star is a short arc.
A round-PSF width (FWHM from moments, or a circular Gaussian) mixes the
trail into the focus and grows with distance from the pole, which is why
astrocam's old 2.4 px "PSF" was wrong. Fit an elliptical Gaussian and
resolve its width onto the local trail direction instead:

  across-trail FWHM  = the focus PSF (independent of exposure and of rho)
  along-trail FWHM   = focus PSF (+) trail length, ~7.4 * sin(rho) binned px
                       on astrocam in 60 s

The across width is the closed-loop focus metric. Take the median over many
stars; one star is noise.

Reference numbers (astrocam, night 2026-10-07, 2x2-binned grey sum,
glow-subtracted, 4656 stars with peak 150-2500): across-trail FWHM by true
lens position 1.22 px at 1.30 rising monotonically to 1.59 px at 1.58;
1.3-1.4 px averaged over the breathing ramp. Along-trail 1.8 px at
rho 0-8 deg, 3.8 px at 32-45 deg. Source script: muppet
~/tmp/skyglow/psf.py (scratch); this module is its fit, lifted out.

Lens timing on astrocam 10-07 (60 s frames, 15-frame sawtooth): the lens
position the IMAGE in frame k saw is header LENSPREP of frame k-1, which is
header LENSPOS (commanded) of frame k-9. Both from correlating per-frame
breathing magnification with the headers (r 0.99). So a commanded move
shows in the image ~9 frames later: a closed loop must wait that long
before judging a step.

Trail direction: the sky turns about the pole, so to first order a trail is
tangential about the pole's pixel (`tangential_angle`). That ignores lens
distortion between star and pole; for an exact direction, project the
star a few seconds later through a fitted camera model (as psf.py does).
"""
from __future__ import annotations

import numpy as np

FWHM = 2.0 * np.sqrt(2.0 * np.log(2.0))   # 2.355: Gaussian sigma -> FWHM


def _g2(xy, a, x0, y0, sx, sy, th, c):
    x, y = xy
    ct, st = np.cos(th), np.sin(th)
    X = (x - x0) * ct + (y - y0) * st
    Y = -(x - x0) * st + (y - y0) * ct
    return a * np.exp(-0.5 * (X ** 2 / sx ** 2 + Y ** 2 / sy ** 2)) + c


def tangential_angle(x, y, pole_x, pole_y):
    """Trail direction (radians, image axes) for stars at x, y circling pole."""
    return np.arctan2(np.asarray(y) - pole_y, np.asarray(x) - pole_x) + np.pi / 2


def fit_star(img, x, y, trail_angle, half=5, peak=(150.0, 2500.0)):
    """(across_fwhm, along_fwhm) of the star nearest (x, y), or None.

    img is background-subtracted. `peak` rejects faint stars (noisy widths)
    and saturated ones (flat tops read as wide); the default suits a
    2x2-binned grey sum of 10-bit IMX708 data and must be rescaled for
    other cameras or binning.
    """
    from scipy.optimize import curve_fit
    xi, yi = int(round(x)), int(round(y))
    H, W = img.shape
    if not (half < xi < W - half - 1 and half < yi < H - half - 1):
        return None
    c = img[yi - half:yi + half + 1, xi - half:xi + half + 1].astype(np.float64)
    if not (peak[0] <= c.max() <= peak[1]):
        return None
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1]
    try:
        p, _ = curve_fit(_g2, ((xx + xi).ravel(), (yy + yi).ravel()), c.ravel(),
                         p0=[c.max(), xi, yi, 1.0, 1.0, 0.0, 0.0], maxfev=4000)
    except Exception:
        return None
    _, _, _, sx, sy, th, _ = p
    sx, sy = abs(sx), abs(sy)
    if not (0.3 < sx < 6 and 0.3 < sy < 6):
        return None
    ang = th - trail_angle
    along = np.hypot(sx * np.cos(ang), sy * np.sin(ang))
    across = np.hypot(sx * np.sin(ang), sy * np.cos(ang))
    return FWHM * across, FWHM * along


def trail_widths(img, xs, ys, trail_angles, **kw):
    """Array (n, 2) of (across, along) FWHM for every star that fits."""
    out = [fit_star(img, x, y, a, **kw) for x, y, a in zip(xs, ys, trail_angles)]
    return np.array([o for o in out if o is not None]).reshape(-1, 2)


def focus_metric(img, xs, ys, trail_angles, min_stars=20, **kw):
    """Median across-trail FWHM over the stars, or nan if too few fit."""
    w = trail_widths(img, xs, ys, trail_angles, **kw)
    return float(np.median(w[:, 0])) if len(w) >= min_stars else float("nan")
