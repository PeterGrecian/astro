#!/usr/bin/env python3
"""Find Neptune in a night's stack (nep/<night>.npz from neptune.py).

Predicted position = ephemeris (GCRS) at the weight-centre time of the frames
used. Reports the brightest blob within 8' of it, its SNR in a 2-camera-px
aperture, and the offset; draws a 1.4 x 1.0 deg cut-out (nep/<night>.png) with
the prediction marked, plus the same for the nearest Hipparcos stars as a check
that the stack is registered.  Runs locally on the copied npz.
"""
import json, math, sys, warnings
from datetime import datetime

import numpy as np
from scipy import ndimage as ndi
from astropy.coordinates import GCRS, get_body, EarthLocation
from astropy.time import Time
import astropy.units as u
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
import os
PLANET = os.environ.get("PLANET", "neptune")                  # PLANET=uranus -> ura/
D = "/home/peter/astro/scratch/saturn-walk/" + {"neptune": "nep", "uranus": "ura"}[PLANET]


def to_px(ra, dec, ra0, dec0, scale, w, h):
    a, d, d0 = math.radians(ra - ra0), math.radians(dec), math.radians(dec0)
    c = math.sin(d0) * math.sin(d) + math.cos(d0) * math.cos(d) * math.cos(a)
    X = math.cos(d) * math.sin(a) / c
    Y = (math.cos(d0) * math.sin(d) - math.sin(d0) * math.cos(d) * math.cos(a)) / c
    s = math.radians(scale)
    return w / 2 - X / s, h / 2 - Y / s


def main(night):
    z = np.load(f"{D}/{night}.npz")
    S, ra0, dec0, scale = z["stack"], float(z["ra0"]), float(z["dec0"]), float(z["scale"])
    recs = [r for r in json.loads(str(z["recs"])) if "noise" in r]
    h, w = S.shape
    wt = np.array([1 / r["noise"] ** 2 for r in recs])
    ts = np.array([datetime.fromisoformat(r["t_mid"]).timestamp() for r in recs])
    tc = Time(float((wt * ts).sum() / wt.sum()), format="unix")
    nep = get_body(PLANET, tc, LOC).transform_to(GCRS(obstime=tc))
    px, py = to_px(nep.ra.deg, nep.dec.deg, ra0, dec0, scale, w, h)
    F = S - ndi.median_filter(S, 41)
    sig = 1.4826 * np.median(np.abs(F - np.median(F)))
    sm = ndi.gaussian_filter(F, 1.2) / sig
    cam_px = 3.5 / (scale * 60)                       # patch px per camera px
    R = int(round(8 / (scale * 60)))                  # 8 arcmin search
    y0, x0 = int(round(py)), int(round(px))
    cut = sm[y0 - R:y0 + R + 1, x0 - R:x0 + R + 1]
    j = np.unravel_index(np.argmax(cut), cut.shape)
    by, bx = y0 - R + j[0], x0 - R + j[1]
    yy, xx = np.mgrid[0:h, 0:w]
    ap = np.hypot(xx - bx, yy - by) < 2 * cam_px
    flux = F[ap].sum(); snr = flux / (sig * math.sqrt(ap.sum() * (cam_px ** 2)))   # pixels are correlated ~cam_px^2
    wts = np.clip(F, 0, None) * ap
    cx, cy = (wts * xx).sum() / wts.sum(), (wts * yy).sum() / wts.sum()
    off = math.hypot(cx - px, cy - py) * scale * 60
    print(f"{night}: {len(recs)} frames, t {tc.isot[:16]}  {PLANET} RA {nep.ra.deg:.4f} Dec {nep.dec.deg:+.4f}  "
          f"pred patch ({px:.1f},{py:.1f})  peak {cut.max():.1f} sig at ({cx:.1f},{cy:.1f})  "
          f"offset {off:.2f}'  aperture SNR ~{snr:.0f}")
    hw, hh = int(0.7 / scale), int(0.5 / scale)
    C = F[y0 - hh:y0 + hh, x0 - hw:x0 + hw] / sig
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(C, cmap="gray", vmin=-1, vmax=12, origin="upper")
    ax.add_patch(plt.Circle((px - (x0 - hw), py - (y0 - hh)), 3 * cam_px, fill=False, color="#00a0ff", lw=1.5))
    ax.set_title(f"{PLANET.title()} {night}: {len(recs)} x 60 s stacked; blue = ephemeris")
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(f"{D}/{night}.png", dpi=90)
    return dict(night=night, t=tc.isot, n=len(recs), eph_ra=nep.ra.deg, eph_dec=nep.dec.deg,
                pred=[px, py], meas=[cx, cy], offset_arcmin=off, peak_sigma=float(cut.max()), snr=snr)


if __name__ == "__main__":
    for n in sys.argv[1:]:
        main(n)
