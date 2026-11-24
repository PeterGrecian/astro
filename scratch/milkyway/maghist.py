"""Stars per magnitude: Gaia DR3 vs what the 7-8 Oct whole-night stack detects, within 3.8 deg of the pole
(mywebsite /astro/project, Peter 2026-11-24, supports "stars down to magnitude 9.7").
Detection as limmag2.py: 5 sigma peaks after Gaussian smoothing (s = 2 drizzle px), matched to Gaia within 3 px,
chance matches removed with a shifted catalogue. Stack: ring-map-subtracted 2x drizzle (rings-deep/driz2-1007).
Usage: maghist.py <stack dir> <cammodel json> <gaia npy (ra, dec, G)> <out prefix>"""
import sys, json, csv, numpy as np, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel, _enu
from astropy.io import fits
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time; import astropy.units as u
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.spatial import cKDTree
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
D, CM, GA, OUT = sys.argv[1:5]
S = fits.getdata(f"{D}/derot-sky.fits", 0).astype(np.float32); h = fits.getheader(f"{D}/derot-sky.fits")
T = Time(h["REFUTC"].replace("+00:00", "")); cm = CameraModel(CM)
fr = AltAz(obstime=T, location=EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg), pressure=0)
def xy(ra, dec):
    a = SkyCoord(np.atleast_1d(ra) * u.deg, np.atleast_1d(dec) * u.deg).transform_to(fr)
    x, y = cm.project(_enu(np.radians(a.az.deg), np.radians(a.alt.deg))); return 2 * np.asarray(x) + 0.5, 2 * np.asarray(y) + 0.5
ra, dec, G = np.load(GA).T; R = 3.8
gx, gy = xy(ra, dec); px, py = xy(0.0, 90.0); px, py = float(px[0]), float(py[0])
rpx = R * cm.f * np.pi / 180 * 2
# detections inside the disc about the pole
yy, xx = np.mgrid[0:S.shape[0], 0:S.shape[1]]
y0, y1, x0, x1 = int(py - rpx - 10), int(py + rpx + 10), int(px - rpx - 10), int(px + rpx + 10)
sub = np.nan_to_num(S[y0:y1, x0:x1]); sm = gaussian_filter(sub, 2.0)
sig = 1.4826 * np.median(np.abs(sm - np.median(sm)))
pk = (sm == maximum_filter(sm, size=9)) & (sm > np.median(sm) + 5 * sig)
dy, dx = np.nonzero(pk); det = np.stack([dx + x0, dy + y0], 1).astype(float)
inner = lambda X, Y: np.hypot(X - px, Y - py) < rpx - 4
det = det[inner(det[:, 0], det[:, 1])]
sel = (dec > 90 - R + 0.05) & inner(gx, gy)
# each detection is credited to the BRIGHTEST Gaia star within 3 px (else a 9.8 star's detection also
# "finds" the 12th-mag stars around it); chance: the same with the detections shifted 60 px
Gs = G[sel]; gt = cKDTree(np.stack([gx[sel], gy[sel]], 1))
def assign(P):
    out = []
    for nb in gt.query_ball_point(P, 3.0):
        if nb: out.append(Gs[nb].min())
    return np.array(out)
ga, gr = assign(det), assign(det + [60, 0])
bins = np.arange(4.0, 13.51, 0.5); rows = []
for lo in bins[:-1]:
    n = int(((Gs >= lo) & (Gs < lo + 0.5)).sum()); na = int(((ga >= lo) & (ga < lo + 0.5)).sum()); nr = int(((gr >= lo) & (gr < lo + 0.5)).sum())
    dn = max(0, na - nr)
    rows.append(dict(g_lo=float(lo), g_hi=float(lo + 0.5), catalogue=n, matched_raw=na, chance=nr, detected=dn,
                     completeness=round(min(1.0, dn / n), 3) if n else None))
g50 = None
for a, b in zip(rows, rows[1:]):
    if a["completeness"] is not None and b["completeness"] is not None and a["completeness"] >= 0.5 > b["completeness"] and a["catalogue"] >= 5:
        ca, cb = a["completeness"], b["completeness"]; g50 = a["g_lo"] + 0.25 + 0.5 * (ca - 0.5) / (ca - cb)
print(f"pole disc r {R} deg: {sel.sum()} Gaia stars, {len(det)} detections; 50% completeness G = {g50:.2f}")
for r in rows: print(r)
with open(OUT + ".csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump(dict(stack=D, refutc=h["REFUTC"], nframes=h["NFRAMES"], disc_deg=R, gaia=GA, detections=len(det), g50=round(g50, 2), bins=rows,
               method="5 sigma peaks (Gaussian s=2, 2x drizzle grid) matched to Gaia DR3 G within 3 px (~1.5 arcmin); chance matches from a catalogue shifted 60 px removed"),
          open(OUT + ".json", "w"), indent=1)
# plot: dark, one axis, two series
BG, INK, MUTE, GRID, CAT, US, AMB = "#000000", "#E0E0E0", "#8E8E93", "#2C2C2E", "#8E8E93", "#0A84FF", "#FF9500"
fig, ax = plt.subplots(figsize=(12, 6.5), dpi=100, facecolor=BG); ax.set_facecolor(BG)
xc = np.array([r["g_lo"] + 0.25 for r in rows]); nc = np.array([r["catalogue"] for r in rows], float); nd = np.array([r["detected"] for r in rows], float)
ax.plot(xc[nc > 0], nc[nc > 0], color=CAT, lw=2, marker="o", ms=8, mec=BG, mew=2, label="Gaia catalogue")
ok = nd > 0
ax.plot(xc[ok], nd[ok], color=US, lw=2, marker="o", ms=8, mec=BG, mew=2, label="detected in our whole-night stack")
ax.set_yscale("log"); ax.set_xlim(3.8, 13.6)
ax.axvline(g50, color=AMB, lw=2, ls=(0, (5, 4)))
ax.text(g50 + 0.12, ax.get_ylim()[1] * 0.6, f"50% found at G {g50:.1f}", color=AMB, fontsize=14, va="top")
i = np.where(ok)[0][-1]
ax.annotate("Gaia catalogue", (xc[-2], nc[-2]), xytext=(-10, 10), textcoords="offset points", ha="right", color=INK, fontsize=13)
ax.annotate("our stack", (xc[i], nd[i]), xytext=(8, -4), textcoords="offset points", color=INK, fontsize=13)
ax.set_xlabel("Gaia G magnitude (fainter to the right), 0.5 mag bins", color=MUTE, fontsize=13)
ax.set_ylabel("stars per bin", color=MUTE, fontsize=13)
ax.tick_params(colors=MUTE, labelsize=12); ax.grid(True, which="major", color=GRID, lw=1); ax.set_axisbelow(True)
for s_ in ax.spines.values(): s_.set_color(GRID)
ax.legend(loc="upper left", frameon=False, labelcolor=INK, fontsize=12)
fig.suptitle(f"How faint we see: stars within {R:g} deg of the pole, astrocam, whole night of 7-8 Oct 2026 ({h['NFRAMES']} x 60 s)",
             color=INK, fontsize=15, x=0.07, ha="left")
ax.set_title("the two curves agree for bright stars; where ours peels away is the limit", color=MUTE, fontsize=12, loc="left")
fig.tight_layout(); fig.savefig(OUT + ".png", facecolor=BG); print("wrote", OUT + ".png")
