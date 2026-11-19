#!/usr/bin/env python3
"""hqfs (FirstScope 76 mm f/3.95 spherical + IMX477 binned 3.1 um px): how far out of focus?
Measures star PSFs (Polaris 0.4 s on 2026-11-13; field stars in 3x3 zones on 11-13 12 s and 11-17 3 s),
and fits each radial profile with a geometric ray trace of the spherical mirror (central obstruction EPS,
assumed) at defocus dz (mm along the axis from the paraxial focus) + gaussian seeing/pixel blur.
Best focus is where the ray-traced EE80 is smallest; the answer is dz_fit - dz_best.
Writes ~/tmp/hqfs-focus/: sheet.png, profiles.png, focus.json."""
import os, csv, json, glob
os.environ["OMP_NUM_THREADS"] = "2"; os.nice(10)
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
BIG = "/mnt/muppet/bigstore/xoverpi-frames/night"
OUT = os.path.expanduser("~/tmp/hqfs-focus"); os.makedirs(OUT, exist_ok=True)
SCALE = 2.29; PXMM = 0.0031; D, F, EPS = 76.0, 300.0, 0.33; SAT = 4000; H = 22
W = np.array([[0.789, 1.172], [1.178, 0.86]]); WMAP = np.tile(W, (760, 1014))
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 13)
yy, xx = np.indices((2 * H + 1, 2 * H + 1)); RR = np.hypot(xx - H, yy - H)

def rows_of(n):
    rs = list(csv.DictReader(open(f"{BIG}/{n}/brightness.csv")))
    for r in rs: r["exp"] = round(float(r["exptime"]), 1); r["med"] = float(r["median"])
    return rs
def load(f):
    with fits.open(f) as h: return h[1].data.astype(np.float32), h[1].header["DATE-OBS"][11:16]
def regcut(a, x, y, h=H):
    c = a[y - h - 4:y + h + 5, x - h - 4:x + h + 5]
    b = np.median(np.r_[c[0], c[-1], c[:, 0], c[:, -1]]); d = np.clip(c - b, 0, None); w = d * (d > 0.1 * d.max())
    Y, X = np.indices(c.shape); cx, cy = (w * X).sum() / w.sum(), (w * Y).sum() / w.sum()
    return ndi.shift(c - b, (h + 4 - cy, h + 4 - cx), order=3)[4:-4, 4:-4]
def metrics(c):
    c = c - np.median(c[RR > H - 2]); tot = c[RR < H - 3].sum(); c = c / tot if tot > 0 else c * 0
    r = np.arange(0, H - 2, 0.5); prof = np.array([c[(RR >= q) & (RR < q + 0.5)].mean() for q in r])
    o = np.argsort(RR.ravel()); ee = np.cumsum(c.ravel()[o]); rs = RR.ravel()[o]
    e50, e80 = rs[min(np.searchsorted(ee, 0.5), rs.size - 1)], rs[min(np.searchsorted(ee, 0.8), rs.size - 1)]
    prof = np.nan_to_num(prof); pk = prof.max(); fw = 2 * r[np.where(prof >= pk / 2)[0].max()] if pk > 0 else np.nan
    return dict(fwhm=fw * SCALE, ee50=2 * e50 * SCALE, ee80=2 * e80 * SCALE, hole=float(prof[0] / pk) if pk > 0 else np.nan), r, prof

# --- geometric model of a spherical mirror, rays at the sensor plane z = F + dz (mm) ---
rng = np.random.default_rng(1); NR = 60000
u = rng.random(NR); hh = np.sqrt(EPS**2 + u * (1 - EPS**2)) * D / 2; ph = rng.random(NR) * 2 * np.pi
R = 2 * F; zm = R - np.sqrt(R**2 - hh**2); zc = R - R / (2 * np.sqrt(1 - (hh / R) ** 2))
# vertex at z=0, centre of curvature at z=R; a ray reflected at height hh (surface z=zm) crosses the axis
# at zc (paraxial -> F, marginal rays closer to the mirror); sensor plane at z = F + dz
def ray_y(dz): return hh * (zc - (F + dz)) / (zc - zm)
def model_prof(dz, sig):
    y = ray_y(dz)
    yx, yyp = y * np.cos(ph) / PXMM + rng.normal(0, sig, NR), y * np.sin(ph) / PXMM + rng.normal(0, sig, NR)
    img, _, _ = np.histogram2d(yyp, yx, bins=2 * H + 1, range=[[-H - .5, H + .5]] * 2)
    return img
def ee80_geo(dz):
    return 2 * np.quantile(np.abs(ray_y(dz)), 0.8) / PXMM * SCALE
DZ = np.round(np.arange(-1.4, 0.81, 0.02), 3)
geo = np.array([ee80_geo(z) for z in DZ]); DZBEST = DZ[np.argmin(geo)]
print(f"ray trace: marginal focus {zc.min() - F:+.3f} mm from paraxial; best (min EE80) dz {DZBEST:+.2f} mm, EE80 {geo.min():.1f}\"", flush=True)
MOD = {}
for z in DZ[::2]:
    for s in (0.8, 1.5, 2.5):
        m = model_prof(z, s); _, _, p = metrics(m); MOD[(z, s)] = p
def fit(prof):
    best = min(MOD, key=lambda k: np.sum((MOD[k] - prof) ** 2)); return best

# --- measurements ---
tiles, results = [], []
def add(label, c):
    m, r, p = metrics(c); (z, s) = fit(p)
    m.update(label=label, dz_from_best=round(float(z - DZBEST), 2), seeing_px=s); results.append((m, r, p, MOD[(z, s)])); tiles.append((label, c, m))
    print(f"{label:28s} FWHM {m['fwhm']:5.1f}\" EE50 {m['ee50']:5.1f}\" EE80 {m['ee80']:5.1f}\" centre/peak {m['hole']:.2f}  -> dz {z - DZBEST:+.2f} mm from best (sig {s})", flush=True)

rs = rows_of("2026-11-13")
runs = []
for i, r in enumerate(rs):
    if runs and runs[-1][0] == r["exp"] and i == runs[-1][1][-1] + 1: runs[-1][1].append(i)
    else: runs.append((r["exp"], [i]))
p04 = [ix for e, ix in runs if e == 0.4 and np.median([rs[i]["med"] for i in ix]) < 300]
for ix in [p04[k] for k in np.linspace(3, len(p04) - 3, 6).astype(int)]:
    cs = []
    for i in ix:
        a, t = load(rs[i]["filename"]); a = a / WMAP; s = ndi.gaussian_filter(a, 4); y, x = np.unravel_index(np.argmax(s), s.shape)
        if not (40 < x < 1988 and 40 < y < 1480): break
        cs.append(regcut(a, x, y))
    if len(cs) > 10: add(f"Polaris 11-13 {t} ({x},{y})", np.mean(cs, axis=0))

def field(night, exp, nfr=50):
    rs = rows_of(night); cand = [i for i, r in enumerate(rs) if r["exp"] == exp and r["med"] < 400]
    pick = cand[::max(len(cand) // nfr, 1)]
    fp = np.median([load(rs[i]["filename"])[0] for i in pick[::2]], axis=0)
    Z = {(zx, zy): [] for zx in range(3) for zy in range(3)}
    for i in pick:
        a, _ = load(rs[i]["filename"]); sat = a >= SAT; a = (a - fp) / WMAP
        s = ndi.gaussian_filter(a, 2.5); noise = 1.4826 * np.median(np.abs(s - np.median(s)))
        mx = (s == ndi.maximum_filter(s, 31)) & (s > 25 * noise)
        for y, x in zip(*np.nonzero(mx)):
            if not (40 < x < 1988 and 40 < y < 1480) or sat[y - 15:y + 16, x - 15:x + 16].any(): continue
            if (mx[y - 30:y + 31, x - 30:x + 31].sum() > 1): continue
            c = regcut(a, x, y); Z[(min(x * 3 // 2028, 2), min(y * 3 // 1520, 2))].append(c / c[RR < H - 3].sum())
    for zy in range(3):
        for zx in range(3):
            L = Z[(zx, zy)]
            if len(L) >= 5: add(f"{night[5:]} {exp:g}s zone {'TMB'[zy]}{'LCR'[zx]} n={len(L)}", np.median(L, axis=0))
field("2026-11-13", 12.0); field("2026-11-17", 3.0)

# --- sheet ---
S = 6; T = (2 * H + 1) * S; cols = 9
img = Image.new("RGB", (cols * (T + 8) + 8, ((len(tiles) + cols - 1) // cols) * (T + 58) + 70), (0, 0, 0)); d = ImageDraw.Draw(img)
d.text((8, 6), f"hqfs PSFs, asinh stretch per tile. Blue circle: 26\" = sphere's least-confusion blur (f/3.95). Bar 10\". {SCALE}\"/px binned", fill=(224, 224, 224), font=FONT)
d.text((8, 24), f"dz = defocus from best focus by ray-trace fit (mm at the sensor; sign: + = sensor farther from mirror; obstruction {EPS} assumed)", fill=(142, 142, 147), font=FONT)
for k, (label, c, m) in enumerate(tiles):
    X0, Y0 = 8 + (k % cols) * (T + 8), 50 + (k // cols) * (T + 58)
    v = np.arcsinh(np.clip(c, 0, None) / (0.02 * c.max())); v = (255 * v / v.max()).astype(np.uint8)
    tile = Image.fromarray(v).resize((T, T), Image.LANCZOS).convert("RGB"); img.paste(tile, (X0, Y0))
    rc = 13 / SCALE * S; cx = X0 + T / 2; cy = Y0 + T / 2; d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], outline=(0, 122, 255))
    L = 10 / SCALE * S; d.line([X0 + 6, Y0 + T - 8, X0 + 6 + L, Y0 + T - 8], fill=(255, 255, 255), width=2)
    md = [r for r in results if r[0]["label"] == label][0][0]
    d.text((X0, Y0 + T + 2), label[:30], fill=(224, 224, 224), font=FONT)
    d.text((X0, Y0 + T + 18), f"EE80 {m['ee80']:.0f}\" FWHM {m['fwhm']:.0f}\"", fill=(142, 142, 147), font=FONT)
    d.text((X0, Y0 + T + 34), f"dz {md['dz_from_best']:+.2f} mm", fill=(255, 149, 0), font=FONT)
img.save(f"{OUT}/sheet.png")
# --- profiles + through-focus curve ---
fig, ax = plt.subplots(1, 2, figsize=(13, 5), facecolor="black")
for a in ax: a.set_facecolor("black"); a.tick_params(colors="#8E8E93"); [s.set_color("#2C2C2E") for s in a.spines.values()]
for m, r, p, mp in results[:6]:
    l, = ax[0].plot(r * SCALE, p / p.max(), lw=1.5, label=m["label"][8:22]); ax[0].plot(r * SCALE, mp / p.max(), "--", color=l.get_color(), lw=0.8)
ax[0].set_xlabel("radius (arcsec)", color="#E0E0E0"); ax[0].set_ylabel("surface brightness / peak", color="#E0E0E0")
ax[0].set_title("Polaris 11-13: measured (solid) vs ray-trace fit (dashed)", color="#E0E0E0"); ax[0].legend(fontsize=7, facecolor="#161616", labelcolor="#E0E0E0")
ax[1].plot(DZ - DZBEST, geo, color="#007AFF"); ax[1].set_xlabel("defocus from best (mm at sensor)", color="#E0E0E0"); ax[1].set_ylabel("geometric EE80 diameter (arcsec)", color="#E0E0E0")
for m, *_ in results: ax[1].plot(m["dz_from_best"], m["ee80"], "o", color="#FF9500", ms=4)
ax[1].set_title("through focus: sphere f/3.95 (line) and measured stars (dots)", color="#E0E0E0")
fig.tight_layout(); fig.savefig(f"{OUT}/profiles.png", dpi=110, facecolor="black")
json.dump([r[0] for r in results], open(f"{OUT}/focus.json", "w"), indent=1)
