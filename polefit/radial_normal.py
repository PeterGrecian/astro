#!/usr/bin/env python3
"""Distortion-immune coarse pole: use only arc points whose NORMAL IS RADIAL.

Peter, 2026-08-14: "the distortion work around is to find the position on the
arcs where lines perpendicular to the tangent are radial from the image center".

WHY IT WORKS. Radial lens distortion displaces points ALONG RAYS from the
distortion centre (~image centre) and does not rotate them. At a point where the
arc's normal is already radial, the distortion displacement is PARALLEL to that
normal: it slides the point along its own normal, changing WHERE the arc sits but
not the DIRECTION of the normal. The normal therefore still points at the true
pole. Anywhere else, the radial displacement has a component tangential to the
arc, which tilts the normal and biases any pole inferred from it.

So these points give unbiased pole constraints with NO distortion model — no
k1/k2 to fit, no correction pass.

GEOMETRY. At a qualifying point the arc normal is radial from the image centre
AND points at the pole, so pole, point and image centre are COLLINEAR. Each
qualifying point therefore constrains the pole to a line through the image
centre; two or more at different azimuths intersect at the pole.

TWO METHODS, deliberately both (they fail differently):
  A) scan along detected arcs for |normal . radial| ~ 1
  B) for each ray from the image centre, find where it crosses an arc
     perpendicularly
A follows the data; B samples azimuth uniformly, so it exposes whether A's
azimuth coverage is too clumped to intersect well.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage


def _arc_normals(img, smooth=2.0, grad_pct=99.0):
    """Bright-ridge points with their local normal direction.

    The image gradient of a bright trail is perpendicular to the trail, i.e. it
    IS the arc normal (up to sign).
    """
    sm = ndimage.gaussian_filter(img, smooth)
    gy, gx = np.gradient(sm)
    mag = np.hypot(gx, gy)
    thr = np.percentile(mag, grad_pct)
    ys, xs = np.nonzero(mag > thr)
    if len(xs) == 0:
        return None
    nx, ny = gx[ys, xs] / mag[ys, xs], gy[ys, xs] / mag[ys, xs]
    return xs.astype(np.float64), ys.astype(np.float64), nx, ny


def method_a(img, centre=None, align_tol=0.02, min_r=40.0):
    """A) Points on arcs whose normal is radial from the image centre.

    Returns (x, y, nx, ny) for qualifying points. align_tol is on
    1 - |normal . radial_unit|, so smaller = stricter.
    """
    got = _arc_normals(img)
    if got is None:
        return None
    xs, ys, nx, ny = got
    H, W = img.shape
    cx, cy = centre or ((W - 1) / 2.0, (H - 1) / 2.0)
    rx, ry = xs - cx, ys - cy
    r = np.hypot(rx, ry)
    keep = r > min_r                     # near the centre the ray is ill-defined
    rx, ry, r = rx[keep], ry[keep], r[keep]
    xs, ys, nx, ny = xs[keep], ys[keep], nx[keep], ny[keep]
    align = np.abs((rx / r) * nx + (ry / r) * ny)      # |n . rhat|
    sel = align >= 1.0 - align_tol
    return xs[sel], ys[sel], nx[sel], ny[sel]


def method_b(img, centre=None, n_rays=180, smooth=2.0, grad_pct=98.0,
             min_r=40.0, align_tol=0.05):
    """B) Walk rays out from the image centre; keep perpendicular arc crossings.

    Samples azimuth UNIFORMLY, which is the point: it reveals whether method A's
    qualifying points are clumped in azimuth (which would make the intersection
    ill-conditioned) rather than silently returning a bad fit.
    """
    sm = ndimage.gaussian_filter(img, smooth)
    gy, gx = np.gradient(sm)
    mag = np.hypot(gx, gy)
    thr = np.percentile(mag, grad_pct)
    H, W = img.shape
    cx, cy = centre or ((W - 1) / 2.0, (H - 1) / 2.0)
    rmax = math.hypot(max(cx, W - cx), max(cy, H - cy))
    out = []
    for k in range(n_rays):
        th = 2 * math.pi * k / n_rays
        ux, uy = math.cos(th), math.sin(th)
        best = None
        rr = np.arange(min_r, rmax, 1.0)
        px = cx + ux * rr
        py = cy + uy * rr
        ok = (px >= 0) & (px < W - 1) & (py >= 0) & (py < H - 1)
        px, py, rr = px[ok], py[ok], rr[ok]
        if len(px) == 0:
            continue
        ix, iy = px.astype(int), py.astype(int)
        m = mag[iy, ix]
        cand = np.nonzero(m > thr)[0]
        for i in cand:
            nxv, nyv = gx[iy[i], ix[i]], gy[iy[i], ix[i]]
            nm = math.hypot(nxv, nyv)
            if nm == 0:
                continue
            nxv, nyv = nxv / nm, nyv / nm
            align = abs(nxv * ux + nyv * uy)
            if align >= 1.0 - align_tol:
                if best is None or m[i] > best[0]:
                    best = (m[i], px[i], py[i], nxv, nyv)
        if best is not None:
            out.append(best[1:])
    if not out:
        return None
    a = np.array(out)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def pole_from_radial_points(xs, ys, centre, img_shape):
    """Intersect the lines (image centre -> qualifying point).

    Each qualifying point is collinear with the image centre and the pole, so
    every point defines a LINE through the centre. Least-squares intersection of
    those lines is the pole. Also returns a conditioning diagnostic: the azimuth
    spread of the points. If they are clumped, the intersection is ill-posed.
    """
    if xs is None or len(xs) < 2:
        return None
    cx, cy = centre
    # Line through (cx,cy) with direction d: points p with (p - c) x d = 0.
    # Stack for least squares on the pole P: for each point, direction
    # d = (x-cx, y-cy) normalised; constraint (P - c) x d = 0.
    A, b = [], []
    az = []
    for x, y in zip(xs, ys):
        dx, dy = x - cx, y - cy
        n = math.hypot(dx, dy)
        if n < 1e-6:
            continue
        dx, dy = dx / n, dy / n
        # (Px - cx)*dy - (Py - cy)*dx = 0
        A.append([dy, -dx])
        b.append(cx * dy - cy * dx)
        az.append(math.degrees(math.atan2(dy, dx)) % 180.0)
    if len(A) < 2:
        return None
    A = np.array(A)
    b = np.array(b)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    az = np.array(az)
    # conditioning: spread of line directions (mod 180). All-parallel = hopeless.
    spread = float(np.percentile(az, 90) - np.percentile(az, 10))
    sv = np.linalg.svd(A, compute_uv=False)
    cond = float(sv[0] / max(sv[-1], 1e-12))
    return float(sol[0]), float(sol[1]), len(A), spread, cond
