"""Smooth sky-glow model and a fixed alt-az camera model.

GlowModel: a night's sky glow is a few fixed spatial modes times per-frame
amplitudes (astrocam 2026-10-07: mode 1 = 99.98% of the variance). Built by
`bin/skyglow-model fit`; each frame's amplitudes are fitted to its own
24-superpixel block medians, so the background costs ~3 numbers per frame.

CameraModel: equidistant-plus-cubic projection about the optical axis of a
camera fixed to the ground (alt-az pointing). Fitted to plate-solve matches
(astrocam, 2026-09-22: 0.3-0.55 px median residual over 179 stars), it maps
any binned-frame pixel to a direction on the sky and back, which is what a
de-rotation needs: a pure image-plane rotation about the pole smears every
star off the optical axis, because the distortion is centred on the axis,
not on the pole.
"""
from __future__ import annotations

import json

import numpy as np

SIDEREAL_RAD_PER_S = 2 * np.pi / 86164.0905


class GlowModel:
    """Green modes [q, Y, X] in `bs`-superpixel blocks over the binned frame.
    The R, G, B glow maps agree in shape to ~2% (2026-10-07), so the green
    modes serve the grey 2x2-sum frame; only the amplitudes are fitted."""

    def __init__(self, path):
        z = np.load(path)
        modes = z["modes"][1] if z["modes"].ndim == 4 else z["modes"]
        self.bs = int(z["bs"]) if "bs" in z else 24
        self.black = 4.0 * float(z["black"]) if "black" in z else 256.0
        self.sky = z["sky"].astype(bool)
        self.modes = modes
        self.M = modes.reshape(len(modes), -1)[:, self.sky.ravel()].T
        self._full = None

    def _upsample(self, h, w):
        from scipy.interpolate import RectBivariateSpline
        ny, nx = self.sky.shape
        yc, xc = (np.arange(ny) + 0.5) * self.bs, (np.arange(nx) + 0.5) * self.bs
        self._full = np.stack([RectBivariateSpline(yc, xc, m)(np.arange(h), np.arange(w))
                               for m in self.modes]).astype(np.float32)

    def fit(self, f):
        """(amplitudes, residual rms of the sky blocks, mean sky level) for a
        black-subtracted binned frame."""
        b = self.bs
        ny, nx = self.sky.shape
        blk = np.median(f[:ny * b, :nx * b].reshape(ny, b, nx, b)
                        .transpose(0, 2, 1, 3).reshape(ny, nx, -1), axis=2)[self.sky]
        amp = np.linalg.lstsq(self.M, blk, rcond=None)[0]
        return amp, float(np.sqrt(np.mean((blk - self.M @ amp) ** 2))), float(blk.mean())

    def subtract(self, frame, return_fit=False):
        f = frame.astype(np.float32) - self.black
        if self._full is None:
            self._upsample(*f.shape)
        amp, rms, level = self.fit(f)
        out = f - np.tensordot(amp, self._full, axes=1)
        return (out, amp, rms, level) if return_fit else out

    def sky_mask(self, shape, erode=1):
        """Full-resolution boolean sky mask, eroded `erode` blocks from the
        foreground so the shifting edges (trees, roof) go too."""
        from scipy.ndimage import binary_erosion
        m = binary_erosion(self.sky, iterations=erode, border_value=0) if erode else self.sky
        full = np.kron(m, np.ones((self.bs, self.bs), bool))
        out = np.zeros(shape, bool)
        h, w = min(shape[0], full.shape[0]), min(shape[1], full.shape[1])
        out[:h, :w] = full[:h, :w]
        return out


def _enu(az, alt):
    return np.stack([np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)], -1)


def _rotate(v, axis, ang):
    """Rodrigues rotation of vectors v[..., 3] about unit `axis` by `ang`."""
    c, s = np.cos(ang), np.sin(ang)
    return v * c + np.cross(axis, v) * s + np.outer(v @ axis, axis).reshape(v.shape) * (1 - c)


class CameraModel:
    def __init__(self, path):
        p = json.load(open(path))
        self.p = p
        self.mirror = p["mirror"]
        self.f, self.k, self.cx, self.cy = p["f"], p["k"], p["cx"], p["cy"]
        b = _enu(np.array(p["az0"]), np.array(p["alt0"]))
        e1 = np.cross([0, 0, 1.0], b); e1 /= np.linalg.norm(e1)
        e2 = np.cross(b, e1)
        cr, sr = np.cos(p["roll"]), np.sin(p["roll"])
        self.b, self.ex, self.ey = b, cr * e1 + sr * e2, -sr * e1 + cr * e2
        lat = np.radians(p["lat"])
        self.pole = np.array([0.0, np.cos(lat), np.sin(lat)])   # celestial pole in ENU

    def project(self, v):
        """ENU unit vectors [..., 3] -> pixel x, y (binned grid)."""
        th = np.arccos(np.clip(v @ self.b, -1, 1))
        phi = np.arctan2(v @ self.ey, v @ self.ex)
        r = self.f * (th + self.k * th ** 3)
        return self.cx + self.mirror * r * np.cos(phi), self.cy - r * np.sin(phi)

    def unproject(self, x, y):
        """Pixel x, y -> ENU unit vectors [..., 3]."""
        dx, dy = (np.asarray(x, float) - self.cx) * self.mirror, -(np.asarray(y, float) - self.cy)
        r = np.hypot(dx, dy) / self.f
        th = r.copy()
        for _ in range(20):                                    # Newton: th + k th^3 = r
            th -= (th + self.k * th ** 3 - r) / (1 + 3 * self.k * th ** 2)
        phi = np.arctan2(dy, dx)
        st = np.sin(th)[..., None]
        return (np.cos(th)[..., None] * self.b
                + st * (np.cos(phi)[..., None] * self.ex + np.sin(phi)[..., None] * self.ey))

    def sky_motion(self, v, dt_s):
        """Where a sky direction at time t0 is at t0 + dt_s (diurnal rotation:
        westward, i.e. clockwise about the pole seen from inside the sphere)."""
        return _rotate(v, self.pole, -SIDEREAL_RAD_PER_S * dt_s)
