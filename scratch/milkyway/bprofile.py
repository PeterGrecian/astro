"""Brightness across the galactic plane, 10-07 vs 10-09 whole-night drizzled stacks.
Median per 1-deg bin of galactic latitude b (stars drop out of a median), over a
common longitude range, well-covered pixels only. A band and a lane at the same
b on both nights are on the sky; a camera-fixed pattern (rings, column bands)
lands at different b because the camera moved ~1 deg between the nights.
Run on muppet with system python3."""
import os, sys, json, warnings, numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro"))
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
from astro.skyglow import CameraModel
A = "/mnt/bigstore/astro-data/astrocam-frames/"
loc = EarthLocation(lat=51.3948*u.deg, lon=-0.2923*u.deg)
N = {"10-07": (A + "2026-10-07/derot-sky-aligned-driz2.fits", A + "2026-10-07/skyglow-cammodel.json", "2026-10-07T23:05:39"),
     "10-09": (os.path.expanduser("~/tmp/derot1009/derot-sky.fits"), A + "2026-10-09/skyglow-cammodel.json", "2026-10-09T22:57:47")}
LMIN, LMAX = 112, 150
bins = np.arange(-25, 25.01, 1.0)
out = {}
for k, (st, cmf, ref) in N.items():
    h = fits.open(st); S = h[0].data.astype(np.float64); W = h["WEIGHT"].data
    H2, W2 = S.shape
    S = np.nanmean(S.reshape(H2 // 2, 2, W2 // 2, 2), axis=(1, 3))     # back to the binned grid
    W = W.reshape(H2 // 2, 2, W2 // 2, 2).mean(axis=(1, 3))
    cm = CameraModel(cmf)
    step = 4
    yy, xx = np.mgrid[0:S.shape[0]:step, 0:S.shape[1]:step]
    v = cm.unproject(xx.astype(float), yy.astype(float))
    alt = np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1))); az = np.degrees(np.arctan2(v[..., 0], v[..., 1])) % 360
    g = SkyCoord(AltAz(az=az.ravel()*u.deg, alt=alt.ravel()*u.deg, obstime=Time(ref), location=loc, pressure=0)).galactic
    l, b = g.l.deg, g.b.deg
    val = S[::step, ::step].ravel(); wt = W[::step, ::step].ravel()
    ok = np.isfinite(val) & (wt > 0.3 * np.nanmax(wt)) & (l > LMIN) & (l < LMAX)
    prof = []
    for lo in bins[:-1]:
        m = ok & (b >= lo) & (b < lo + 1)
        prof.append(float(np.median(val[m])) if m.sum() > 30 else None)
    noise = 1.4826 * np.nanmedian(np.abs(val[ok] - np.nanmedian(val[ok])))
    out[k] = {"profile": prof, "pix_noise": float(noise)}
    print(k, "n", ok.sum(), "noise", round(noise, 3))
json.dump({"b": bins[:-1].tolist(), "l": [LMIN, LMAX], "nights": out}, open("bprofile.json", "w"), indent=1)
print(" b    10-07   10-09")
for i, b0 in enumerate(bins[:-1]):
    f = lambda x: "   -  " if x is None else f"{x:7.3f}"
    print(f"{b0:+4.0f} {f(out['10-07']['profile'][i])} {f(out['10-09']['profile'][i])}")
