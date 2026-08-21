#!/usr/bin/env python3
"""polefit — celestial pole from a max stack. Arcs find Polaris; Polaris finds the pole.

See README.md for why the two stages are split and the measured evidence.

Public API:
    fit_pole(image, plate_scale_deg_px, ...) -> PoleFit | None
"""
from __future__ import annotations

import math
import pathlib
import sys
from dataclasses import dataclass, asdict

import numpy as np
from scipy import ndimage

# Polaris–NCP separation is NOT a constant to hardcode. Precession shrinks it
# fast in fractional terms — 0.736 deg at J2000, 0.626 deg in 2026 — and this
# figure is the SELECTOR that picks Polaris out of the candidate arcs (see
# fit_pole), so a stale value can select the wrong star, not merely misreport
# the expected radius. It used to be pinned at 0.7525 (a mid-1990s value, 20%
# high); it now comes from astro.skypos for the epoch of the frame.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from astro.skypos import polaris_pole_distance  # noqa: E402


@dataclass
class PoleFit:
    x: float
    y: float
    radius_px: float
    expected_radius_px: float
    sweep_deg: float
    residual_px: float
    n_arc_px: int
    coarse_x: float
    coarse_y: float
    stage1_shift_px: float

    def as_dict(self):
        return asdict(self)


def _coarse_centre(img, gradient_pct=99.0, smooth=1.5):
    """STAGE 1 — consensus centre from many arcs.

    For a circular arc the image gradient is RADIAL (perpendicular to the
    trail), so at the true centre (P-C) is parallel to grad I everywhere.
    Minimise the median |cross product|. Deliberately coarse: this only has to
    localise Polaris, not be the answer.
    """
    gy, gx = np.gradient(ndimage.gaussian_filter(img, smooth))
    mag = np.hypot(gx, gy)
    ys, xs = np.nonzero(mag > np.percentile(mag, gradient_pct))
    if len(xs) < 200:
        return None
    g = np.stack([gx[ys, xs], gy[ys, xs]], 1)
    g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-9
    H, W = img.shape

    def score(cx, cy):
        dx, dy = xs - cx, ys - cy
        r = np.hypot(dx, dy) + 1e-9
        return float(np.median(np.abs(dx / r * g[:, 1] - dy / r * g[:, 0])))

    best = None
    for cy in range(0, H, max(1, H // 24)):
        for cx in range(0, W, max(1, W // 24)):
            s = score(cx, cy)
            if best is None or s < best[0]:
                best = (s, cx, cy)
    _, cx0, cy0 = best
    for step in (max(H // 48, 8), 4, 2):
        for cy in range(cy0 - 2 * step, cy0 + 3 * step, step):
            for cx in range(cx0 - 2 * step, cx0 + 3 * step, step):
                s = score(cx, cy)
                if s < best[0]:
                    best = (s, cx, cy)
        _, cx0, cy0 = best
    return float(best[1]), float(best[2])


def _find_polaris_arc(img, cx, cy, search_px, bright_pct=99.5, radius_hint=None):
    """STAGE 1b — the brightest arc near the coarse centre is Polaris.

    Returns the pixel coordinates of that arc. The crop must be generous: a
    too-tight crop captures only a FRAGMENT, and a short angular sweep cannot
    constrain a circle centre (measured: a 20 px fragment gave radius 10.9 px
    against 18.1 expected, and a centre 90 px wrong).
    """
    H, W = img.shape
    x0, x1 = int(max(0, cx - search_px)), int(min(W, cx + search_px))
    y0, y1 = int(max(0, cy - search_px)), int(min(H, cy + search_px))
    sub0 = img[y0:y1, x0:x1]
    if sub0.size == 0:
        return None

    # RE-CENTRE ON POLARIS FIRST. The stage-1 consensus centre can sit ~90 px
    # from the true pole (measured), so a crop centred on it either misses
    # Polaris's arc entirely or, if widened, drags in neighbouring arcs and the
    # circle fit collapses (radius 6-11 px against 18.1 expected). Find the
    # brightest pixel in the search box, then re-crop TIGHTLY around that: the
    # arc must be isolated, and it is only ~2x the Polaris radius across.
    # Which bright object is Polaris? NOT simply the brightest in the box: a
    # brighter star elsewhere in the box yields an arc of similar radius and the
    # fit lands 103 px wrong (measured 2026-08-14). The discriminator is that
    # POLARIS'S ARC IS CENTRED ON THE POLE — i.e. its arc lies at radius ~r_exp
    # from the coarse centre. So look for bright pixels in an ANNULUS about the
    # coarse centre at the expected Polaris radius.
    if radius_hint:
        yy, xx = np.mgrid[y0:y1, x0:x1]
        rr = np.hypot(xx - cx, yy - cy)
        ann = np.abs(rr - radius_hint) <= max(6.0, 0.5 * radius_hint)
        if ann.sum() >= 12:
            masked = np.where(ann, sub0, -np.inf)
            py0, px0 = np.unravel_index(int(np.argmax(masked)), masked.shape)
        else:
            py0, px0 = np.unravel_index(int(np.argmax(sub0)), sub0.shape)
    else:
        py0, px0 = np.unravel_index(int(np.argmax(sub0)), sub0.shape)
    bx, by = px0 + x0, py0 + y0
    # Pad from the EXPECTED radius: the arc spans at most ~2.2r, and the
    # brightest pixel can sit at either end, so 1.6r each way suffices while
    # staying clear of the next arc out.
    pad = int(max(14, 1.6 * radius_hint)) if radius_hint else 30
    x0, x1 = int(max(0, bx - pad)), int(min(W, bx + pad))
    y0, y1 = int(max(0, by - pad)), int(min(H, by + pad))
    sub = img[y0:y1, x0:x1]
    if sub.size == 0:
        return None

    # Threshold RELATIVE TO THE BRIGHTEST THING PRESENT, not to a percentile of
    # the crop. The crop is mostly dark sky, so a percentile threshold lands far
    # too low: the arc then merges with noise and fragments, and the circle fit
    # returns a radius of 4-11 px against 18.1 expected (measured 2026-08-14).
    # Polaris is the brightest object near the pole and is typically saturated,
    # so a fraction of the crop maximum isolates it cleanly.
    peak = float(sub.max())
    best = None
    for frac in (0.85, 0.7, 0.55, 0.4):
        # ALL pixels above threshold, NOT the largest connected component.
        # Measured 2026-08-14: JPEG artefacts and saturation break Polaris's arc
        # into fragments, so "largest component" returns one piece and fits
        # r~11 at EVERY threshold, against 18.1 expected. Using all bright
        # pixels in the (already tight) crop fits r=17.5-18.4 correctly.
        ys, xs = np.nonzero(sub > frac * peak)
        if len(xs) < 12:
            continue
        # prefer the threshold giving the largest angular sweep — that is what
        # constrains the centre
        fit = _fit_circle(xs.astype(np.float64), ys.astype(np.float64))
        sweep = fit[4] if fit else 0.0
        if best is None or sweep > best[0]:
            best = (sweep, xs, ys)
    if best is None:
        return None
    _, xs, ys = best

    # NO GROWTH LOOP. An earlier version re-cropped around the arc's bounding
    # box and re-extracted; it ran away, swallowing neighbouring arcs (304 px,
    # r=46.1 against 18.1 expected). The crop below is sized from the EXPECTED
    # radius instead, which is known a priori — Polaris's arc cannot be larger
    # than ~2.2x its radius across, so a fixed pad is both sufficient and safe.
    return xs + x0, ys + y0


def _fit_circle(X, Y):
    """Kasa algebraic circle fit. Returns (cx, cy, r, residual_median, sweep_deg)."""
    A = np.c_[X, Y, np.ones(len(X))]
    b = -(X.astype(np.float64) ** 2 + Y.astype(np.float64) ** 2)
    (D, E, F), *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = -D / 2.0, -E / 2.0
    disc = cx * cx + cy * cy - F
    if disc <= 0:
        return None
    r = math.sqrt(disc)
    resid = float(np.median(np.abs(np.hypot(X - cx, Y - cy) - r)))
    # Angular sweep, wrap-safe. A naive max-min is wrong whenever the arc
    # straddles the +-180 branch cut: a real 138 deg arc was reported as 349 deg
    # (measured 2026-08-14), which then failed a sweep gate it should have
    # passed. Correct method: sort the angles, find the LARGEST GAP between
    # consecutive samples, and the sweep is 360 minus that gap.
    th = np.sort(np.degrees(np.arctan2(Y - cy, X - cx)) % 360.0)
    if len(th) < 2:
        return None
    gaps = np.diff(np.concatenate([th, th[:1] + 360.0]))
    sweep = float(360.0 - gaps.max())
    return float(cx), float(cy), r, resid, sweep


def fit_pole(img, plate_scale_deg_px, search_px=140, min_sweep_deg=60.0,
             radius_tol=0.25, coarse=None, max_candidates=12, epoch=None):
    """Fit the celestial pole. Returns PoleFit, or None if nothing passes.

    plate_scale_deg_px must match THIS image (a half-res max.jpg has twice the
    per-pixel scale of the full-res frames). `epoch` is the fractional year the
    frame was taken; it sets the Polaris–pole separation and defaults to now.

    STRATEGY. Stage 1 is only accurate to ~90 px (measured), which is not enough
    to pick Polaris by proximity — a brighter star nearby yields an arc of
    similar radius and the answer lands ~100 px wrong. So instead of trusting
    stage 1 to identify Polaris, TEST CANDIDATES: take the brightest local peaks
    within search_px of the coarse centre and fit each one's arc, then keep the
    candidate whose fitted radius best matches the known Polaris-NCP separation.
    The self-check thus becomes the SELECTOR, not merely a final gate — which is
    what makes the method robust to stage 1 being poor.
    """
    img = np.asarray(img, dtype=np.float32)
    c = coarse or _coarse_centre(img)
    if c is None:
        return None
    cx0, cy0 = c
    expected = polaris_pole_distance(epoch) / plate_scale_deg_px
    H, W = img.shape

    # Local maxima within the search box, brightest first, thinned so that
    # candidates are distinct objects rather than neighbouring pixels of one.
    x0, x1 = int(max(0, cx0 - search_px)), int(min(W, cx0 + search_px))
    y0, y1 = int(max(0, cy0 - search_px)), int(min(H, cy0 + search_px))
    box = img[y0:y1, x0:x1]
    if box.size == 0:
        return None
    mx = ndimage.maximum_filter(box, size=int(max(5, expected)))
    peaks = (box == mx) & (box > np.percentile(box, 95))
    pys, pxs = np.nonzero(peaks)
    if len(pxs) == 0:
        return None
    order = np.argsort(box[pys, pxs])[::-1][:max_candidates]

    best = None
    for i in order:
        bx, by = int(pxs[i] + x0), int(pys[i] + y0)
        pad = int(max(14, 1.6 * expected))
        sx0, sx1 = max(0, bx - pad), min(W, bx + pad)
        sy0, sy1 = max(0, by - pad), min(H, by + pad)
        sub = img[sy0:sy1, sx0:sx1]
        if sub.size == 0:
            continue
        peak = float(sub.max())
        for frac in (0.85, 0.7, 0.55, 0.4):
            ys, xs = np.nonzero(sub > frac * peak)
            if len(xs) < 12:
                continue
            fit = _fit_circle(xs.astype(np.float64) + sx0,
                              ys.astype(np.float64) + sy0)
            if fit is None:
                continue
            px, py, r, resid, sweep = fit
            if sweep < min_sweep_deg:
                continue
            if abs(r - expected) > radius_tol * expected:
                continue
            # score: radius agreement first, then tight residual
            score = abs(r - expected) / expected + 0.02 * resid
            if best is None or score < best[0]:
                best = (score, PoleFit(
                    x=px, y=py, radius_px=r, expected_radius_px=expected,
                    sweep_deg=sweep, residual_px=resid, n_arc_px=int(len(xs)),
                    coarse_x=cx0, coarse_y=cy0,
                    stage1_shift_px=float(math.hypot(px - cx0, py - cy0))))
    return best[1] if best else None
