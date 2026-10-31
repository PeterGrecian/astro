#!/usr/bin/env python3
"""Star count against magnitude in the fshq 1-in-10 still, clear part of the night, against Gaia DR3."""
import os, warnings
os.environ["OMP_NUM_THREADS"] = "1"
os.nice(15)
warnings.filterwarnings("ignore")
import numpy as np
from scipy import ndimage as ndi
from astropy.io import fits
from astropy.wcs import WCS
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.expanduser("~/tmp/fshq-survey")
img = np.load(f"{OUT}/night_still_raw_v2.npy"); fr = np.load(f"{OUT}/night_still_frames_v2.npy")
good = fr >= 60
raw = img.mean(axis=0)
l = np.mean([p / (1.4826 * np.median(np.abs(p[good]))) for p in img], axis=0)
H, W = raw.shape
yy, xx = np.mgrid[:H, :W]
POLE = (1000.8, 1000.8); PER = np.radians(15.0411 * 3 / 3600)
crossing = (17 + 40 / 60 + (7449 + np.arctan2(xx - POLE[0], POLE[1] - yy) / PER) * 3 / 3600 - 17) % 24 + 17   # hours from 17:00 on
clear = good & (crossing < 27.75)    # before 03:45

def aperture(x, y):
    d = np.hypot(xx - x, yy - y)
    ap = d <= 14; ann = (d > 18) & (d <= 28) & good
    return float((raw[ap] - np.median(raw[ann])).sum()) if ann.sum() > 50 else np.nan

sm = ndi.gaussian_filter(l, 2)
s = 1.4826 * np.median(np.abs(sm[good]))
lab, n = ndi.label((sm > 6 * s) & good)
idx = range(1, n + 1)
cm = np.array(ndi.center_of_mass(np.clip(raw, 0, None), lab, idx))
area = np.array(ndi.sum(lab > 0, lab, idx))
oy, ox = cm[:, 0], cm[:, 1]
inclear = clear[oy.astype(int), ox.astype(int)]
print("blobs", n, "in clear part", inclear.sum(), "small <30 px", ((area < 30) & inclear).sum(), "huge >2000 px", ((area > 2000) & inclear).sum())
keep = (area >= 30) & (area < 2000) & inclear
flux = np.array([aperture(x, y) for x, y in zip(ox[keep], oy[keep])])
kx, ky = ox[keep], oy[keep]

w = WCS(fits.getheader(f"{OUT}/solve/stars.xy.wcs"))
# Gaia DR3, VizieR, 4 deg cone about the pole to G 13.5 (the cached gaia_near_pole.npy is off-centre and misses most of the arch)
ra, dec, mag = np.load(f"{OUT}/gaia_pole_4deg_G13.5.npy").T
px, py = w.all_world2pix(np.c_[ra, dec], 0).T
ins = (px >= 0) & (px < W) & (py >= 0) & (py < H)
ins[ins] = clear[py[ins].astype(int), px[ins].astype(int)]
cat_mag = mag[ins]; cx, cy = px[ins], py[ins]
print("Gaia stars in this sky", len(cat_mag), "G<10", (cat_mag < 10).sum(), "G<11", (cat_mag < 11).sum(), "G<12", (cat_mag < 12).sum())

kdec = w.all_pix2world(np.c_[kx, ky], 0)[:, 1]
incone = kdec > 86.05
print("detections", len(kx), "inside the Gaia cone", incone.sum())
kx, ky, flux = kx[incone], ky[incone], flux[incone]

# each detection takes the brightest Gaia star within 5 px, down to G 12.5
bright = cat_mag < 12.5
bx, by, bm = cx[bright], cy[bright], cat_mag[bright]
bidx = np.nonzero(bright)[0]
matched = np.zeros(len(kx), bool); cat_matched = np.zeros(len(cat_mag), bool); det_g = np.full(len(kx), np.nan); sep = np.full(len(kx), np.nan)
for i in range(len(kx)):
    d = np.hypot(bx - kx[i], by - ky[i])
    near = np.nonzero(d < 5)[0]
    if len(near):
        j = near[np.argmin(bm[near])]
        matched[i] = True; cat_matched[bidx[j]] = True; det_g[i] = bm[j]; sep[i] = d[j]
# how often would a random spot find such a star? shift the detections and repeat
rng = np.random.default_rng(1)
chance = []
for _ in range(200):
    sx = kx + rng.uniform(40, 120) * rng.choice([-1, 1]); sy = ky + rng.uniform(40, 120) * rng.choice([-1, 1])
    chance.append(sum((np.hypot(bx - a, by - b) < 5).any() for a, b in zip(sx, sy)))
print("matched", matched.sum(), "of", len(kx), "median separation px", round(float(np.nanmedian(sep)), 2), "chance matches expected", round(float(np.mean(chance)), 1))
zps = (det_g + 2.5 * np.log10(np.clip(flux, 0.01, None)))[matched & (flux > 0)]
zp = np.median(zps)
print("zero point (G)", round(float(zp), 2), "scatter", round(float(1.4826 * np.median(np.abs(zps - zp))), 2))
print("unmatched detections, calibrated G:", np.round(np.sort(zp - 2.5 * np.log10(np.clip(flux[~matched], 0.01, None))), 1))

bins = np.arange(4.0, 12.51, 0.5)
hd, _ = np.histogram(cat_mag[cat_matched], bins); hc, _ = np.histogram(cat_mag, bins)
print("G bin   Gaia  detected  percent")
for b, c, m in zip(bins[:-1], hc, hd):
    print(f"{b:.1f}-{b + .5:.1f}  {c:4d}  {m:3d}  {100 * m / c if c else 0:3.0f}%")

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": "#E0E0E0", "axes.labelcolor": "#8E8E93", "xtick.color": "#8E8E93", "ytick.color": "#8E8E93"})
fig, ax = plt.subplots(figsize=(11, 6.2), dpi=120, facecolor="#000000")
ax.set_facecolor("#000000")
wd = 0.2; c = bins[:-1] + 0.25
ax.bar(c - wd / 2 - 0.01, hd, wd, color="#007AFF", label=f"Gaia stars detected in the still ({cat_matched.sum()})")
ax.bar(c + wd / 2 + 0.01, hc, wd, color="#8E8E93", label=f"All Gaia DR3 stars, same sky ({(cat_mag < 12.5).sum()} to G 12.5)")
for sp in ("top", "right", "left"):
    ax.spines[sp].set_visible(False)
ax.spines["bottom"].set_color("#2C2C2E")
ax.grid(axis="y", color="#2C2C2E", linewidth=1); ax.set_axisbelow(True)
ax.tick_params(length=0)
ax.set_xticks(bins[::2]); ax.set_xlim(3.9, 12.6)
ax.set_xlabel("Gaia G magnitude (fainter to the right)")
ax.set_ylabel("Stars per 0.5 mag")
ax.set_title("fshq, night of 2026-10-30: stars by Gaia G, clear part of the night (before 03:45), 1 frame in 10", loc="left", fontsize=13, color="#E0E0E0")
ax.legend(loc="upper left", frameon=False, labelcolor="#E0E0E0")
fig.tight_layout()
fig.savefig(f"{OUT}/mag_hist.png", facecolor="#000000")
