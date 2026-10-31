#!/usr/bin/env python3
"""Plate-solve the fshq night still from its ring centroids (astrometry.net, Tycho-2), then name the rings from HYG."""
import csv, os, subprocess
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "1"
os.nice(15)
import numpy as np
from scipy import ndimage as ndi
from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS

OUT = os.path.expanduser("~/tmp/fshq-survey")
SOLVE = f"{OUT}/solve"; os.makedirs(SOLVE, exist_ok=True)
img = np.load(f"{OUT}/night_still_raw_v2.npy"); fr = np.load(f"{OUT}/night_still_frames_v2.npy")
good = fr >= 60
l = np.mean([p / (1.4826 * np.median(np.abs(p[good]))) for p in img], axis=0)
raw = img.mean(axis=0)
sm = ndi.gaussian_filter(l, 2)
s = 1.4826 * np.median(np.abs(sm[good]))
lab, n = ndi.label((sm > 6 * s) & good)
idx = range(1, n + 1)
fl = ndi.sum(np.clip(raw, 0, None), lab, idx)
cm = np.array(ndi.center_of_mass(np.clip(raw, 0, None), lab, idx))
area = ndi.sum(lab > 0, lab, idx)
keep = (area >= 30) & (area < 2000)
o = np.argsort(-fl[keep])
oy, ox, of, oa = cm[keep][o, 0], cm[keep][o, 1], fl[keep][o], area[keep][o]
print("objects for solving", len(ox))
Table({"X": ox + 1, "Y": oy + 1, "FLUX": of}).write(f"{SOLVE}/stars.xy.fits", overwrite=True)
r = subprocess.run(["solve-field", "--overwrite", "--no-plots", "--scale-units", "arcsecperpix", "--scale-low", "10", "--scale-high", "15",
                    "--width", "2000", "--height", str(raw.shape[0]), "--x-column", "X", "--y-column", "Y", "--sort-column", "FLUX",
                    "--ra", "0", "--dec", "90", "--radius", "6", "--cpulimit", "180", "--dir", SOLVE, f"{SOLVE}/stars.xy.fits"],
                   capture_output=True, text=True, timeout=280)
print("\n".join(x for x in r.stdout.splitlines() if any(k in x for k in ("Field center", "Field size", "Field rotation", "pixel scale", "solved", "Did not", "RA,Dec"))))
if r.returncode or not os.path.exists(f"{SOLVE}/stars.xy.wcs"):
    print("not solved", r.stderr[-400:]); raise SystemExit
w = WCS(fits.getheader(f"{SOLVE}/stars.xy.wcs"))
scale = abs(w.pixel_scale_matrix.diagonal()).max() * 3600 if False else np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix))) * 3600
print(f"scale {scale:.3f} arcsec/px, focal length {300 * 12.52 / scale:.1f} mm against nominal 300, handedness det {np.linalg.det(w.pixel_scale_matrix):+.3e}")
print("NCP (J2000) at px", np.round(w.all_world2pix([[0.0, 90.0]], 0)[0], 1))
rd = w.all_pix2world(np.c_[ox, oy], 0)
print("Object RA Dec at centre of each ring; nearest HYG star")
rows = list(csv.DictReader(open(f"{OUT}/hyg.csv")))
rows = [x for x in rows if x["dec"] and float(x["dec"]) > 84]
ra = np.array([float(x["ra"]) * 15 for x in rows]); dec = np.array([float(x["dec"]) for x in rows]); mag = np.array([float(x["mag"]) for x in rows])
print("HYG stars above dec 84:", len(rows))
pxs = w.all_world2pix(np.c_[ra, dec], 0)
print("rank x y flux area | sep_px mag name hip hd dist-from-NCP")
for i in range(min(40, len(ox))):
    d = np.hypot(pxs[:, 0] - ox[i], pxs[:, 1] - oy[i])
    # prefer the brightest star inside a ring radius rather than the nearest of many faint ones
    near = np.nonzero(d < 12)[0]
    j = near[np.argmin(mag[near])] if len(near) else d.argmin()
    x = rows[j]
    nm = " ".join(t for t in (x.get("proper", ""), x.get("bf", "")) if t)
    print(i + 1, f"{ox[i]:.0f} {oy[i]:.0f} {of[i]:.0f} {oa[i]:.0f} | {d[j]:.1f} {mag[j]:.2f}", (nm or "-"), f"HIP{x['hip']} HD{x['hd']}", f"{90 - dec[j]:.2f}", "" if d[j] < 12 else "(NO MATCH)")
print("\nBright HYG stars that should be inside the arch")
insky = (pxs[:, 0] > 0) & (pxs[:, 0] < 2000) & (pxs[:, 1] > 0) & (pxs[:, 1] < raw.shape[0])
for j in np.argsort(mag):
    if not insky[j] or mag[j] > 6.8:
        continue
    px_, py_ = pxs[j]
    if fr[int(py_), int(px_)] < 60:
        continue
    x = rows[j]
    d = np.hypot(ox - px_, oy - py_).min()
    print(f"mag {mag[j]:.2f} {x.get('proper', '')} {x.get('bf', '')} HIP{x['hip']} HD{x['hd']} at {px_:.0f},{py_:.0f}, nearest object {d:.1f} px")
