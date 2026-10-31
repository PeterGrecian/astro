#!/usr/bin/env python3
"""Star colours from the fshq all-frames still: our B-R against Gaia BP-RP, colour histogram, white balance."""
import os, warnings, csv
os.environ["OMP_NUM_THREADS"] = "1"
os.nice(15)
warnings.filterwarnings("ignore")
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.expanduser("~/tmp/fshq-survey")
# the daemon labels these frames SRGGB, but libcamera delivers SBGGR here: channel 0 is really blue, so swap
img = np.load(f"{OUT}/night_still_raw_all.npy")[::-1]; fr = np.load(f"{OUT}/night_still_frames_all.npy")
good = fr >= 600
H, W = fr.shape
yy, xx = np.mgrid[:H, :W]
POLE = (1000.8, 1000.8); PER = np.radians(15.0411 * 3 / 3600)
crossing = (17 + 40 / 60 + (7449 + np.arctan2(xx - POLE[0], POLE[1] - yy) / PER) * 3 / 3600 - 17) % 24 + 17
clear = good & (crossing < 27.75)
w = WCS(fits.getheader(f"{OUT}/solve/stars.xy.wcs"))
rows = [l.rstrip("\n").split("\t") for l in open(f"{OUT}/gaia_col.tsv") if l[:1].isdigit()]
rows = [r for r in rows if len(r) >= 4 and r[2].strip() and r[3].strip()]
ra, dec, g, bprp = np.array([[float(x) for x in r[:4]] for r in rows]).T
px, py = w.all_world2pix(np.c_[ra, dec], 0).T
ok = (px > 30) & (px < W - 30) & (py > 30) & (py < H - 30)
ok[ok] = clear[py[ok].astype(int), px[ok].astype(int)]
ra, dec, g, bprp, px, py = ra[ok], dec[ok], g[ok], bprp[ok], px[ok], py[ok]
print("Gaia stars G<12 in the clear part", len(g))
stars = []
for j in np.argsort(g):
    if g[j] > 11:
        break
    # brighter neighbour inside the apertures spoils the colour
    d2 = np.hypot(px - px[j], py - py[j])
    if ((d2 > 0) & (d2 < 30) & (g < g[j] + 2)).any():
        continue
    d = np.hypot(xx - px[j], yy - py[j])
    ap = d <= 14; ann = (d > 18) & (d <= 28) & good
    if ann.sum() < 100:
        continue
    f = []; e = []
    for c in range(3):
        bg = np.median(img[c][ann])
        f.append((img[c][ap] - bg).sum())
        e.append(1.4826 * np.median(np.abs(img[c][ann] - bg)) * ap.sum() ** .5)
    f, e = np.array(f), np.array(e)
    if (f / e).min() < 10:
        continue
    stars.append((g[j], bprp[j], px[j], py[j], ra[j], dec[j], *f, *(f / e)))
s = np.array(stars)
print("stars with S/N >= 10 in all three colours, no bright neighbour:", len(s))
G, C, X, Y, RA, DEC, FR, FG, FB, SR, SG, SB = s.T
br = -2.5 * np.log10(FB / FR)
gr = -2.5 * np.log10(FG / FR)
fit = np.polyfit(C, br, 1)
res = br - np.polyval(fit, C)
print(f"our B-R = {fit[0]:.3f} * (BP-RP) + {fit[1]:.3f}, scatter {1.4826 * np.median(np.abs(res - np.median(res))):.3f} mag, BP-RP range {C.min():.2f}..{C.max():.2f}, ours {br.min():.2f}..{br.max():.2f}")
fitg = np.polyfit(C, gr, 1)
print(f"our G-R = {fitg[0]:.3f} * (BP-RP) + {fitg[1]:.3f}")
# white balance: gains that make a solar colour star (BP-RP 0.82) grey
br0, gr0 = np.polyval(fit, 0.82), np.polyval(fitg, 0.82)
gb = 10 ** (0.4 * br0); gg = 10 ** (0.4 * gr0)
print(f"gains for grey at BP-RP 0.82: R 1.000 G {gg:.3f} B {gb:.3f}")
# the still again, red and blue the right way round and balanced on a solar-colour star; no frames re-read
from PIL import Image
gain = np.array([1.0, gg, gb])
wb = np.zeros_like(img)
for c in range(3):
    v = img[c][good]
    wb[c] = (img[c] - v[np.abs(v - np.median(v)) < 0.5].mean()) * gain[c]
sig = 1.4826 * np.median(np.abs(wb.mean(axis=0)[good]))
rgb = wb / sig
lum = rgb.mean(axis=0)
fade = np.clip(fr / 1200, 0, 1) ** 0.7
top = np.percentile(lum[good], 99.97)
out = np.clip(np.arcsinh(np.clip(rgb + 0.5, 0, None) / 3) / np.arcsinh((top + 0.5) / 3), 0, 1) * fade
final = np.pad((255 * out.transpose(1, 2, 0)).astype(np.uint8), ((100, 100), (100, 100), (0, 0)))
Image.fromarray(final).save(f"{OUT}/night_still_2k_colour.png")
print("noise by channel after balance", [round(float(1.4826 * np.median(np.abs(wb[c][good]))), 4) for c in range(3)])
print("G BP-RP ourB-R ourG-R x y S/N(R,G,B) (sorted by BP-RP)")
for i in np.argsort(C):
    print(f"{G[i]:5.2f} {C[i]:5.2f} {br[i]:6.2f} {gr[i]:6.2f} {X[i]:5.0f} {Y[i]:5.0f} {SR[i]:5.0f} {SG[i]:5.0f} {SB[i]:5.0f}")
with open(f"{OUT}/star_colours.csv", "w", newline="") as fh:
    wr = csv.writer(fh); wr.writerow("G bp_rp our_b_r our_g_r x y ra dec f_r f_g f_b".split())
    for i in np.argsort(C):
        wr.writerow([round(float(v), 4) for v in (G[i], C[i], br[i], gr[i], X[i], Y[i], RA[i], DEC[i], FR[i], FG[i], FB[i])])

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": "#E0E0E0", "axes.labelcolor": "#8E8E93", "xtick.color": "#8E8E93", "ytick.color": "#8E8E93"})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6), dpi=120, facecolor="#000000")
def style(ax):
    ax.set_facecolor("#000000")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#2C2C2E")
    ax.tick_params(length=0); ax.set_axisbelow(True)
style(a1); style(a2)
bins = np.arange(np.floor(br.min() * 4) / 4, np.ceil(br.max() * 4) / 4 + 0.01, 0.25)
a1.hist(br, bins, color="#007AFF", rwidth=0.8)
a1.grid(axis="y", color="#2C2C2E")
a1.set_xlabel("Our colour, B−R magnitudes (bluer to the left, uncalibrated zero)"); a1.set_ylabel("Stars per 0.25 mag")
a1.set_title(f"{len(s)} stars by colour", loc="left", fontsize=13)
a2.grid(color="#2C2C2E")
xl = np.array([C.min(), C.max()])
a2.plot(xl, np.polyval(fit, xl), color="#8E8E93", linewidth=2, zorder=1)
a2.scatter(C, br, s=64, color="#007AFF", edgecolors="#000000", linewidths=2, zorder=2)
a2.set_xlabel("Gaia BP−RP (bluer to the left)"); a2.set_ylabel("Our B−R magnitudes")
a2.set_title(f"Our colour against Gaia: slope {fit[0]:.2f}, scatter {1.4826 * np.median(np.abs(res - np.median(res))):.2f} mag", loc="left", fontsize=13)
fig.suptitle("fshq, night of 2026-10-30, all frames, before 03:45, no IR filter", x=0.01, ha="left", color="#8E8E93", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(f"{OUT}/star_colours.png", facecolor="#000000")
