#!/usr/bin/env python3
"""Saturn walking against the stars, rendered the way nep-render.py renders
Neptune: an even clock (STEP days per frame) with cross-fades between the
measured nights, a ROLLING star stack (Gaussian in time, sigma TAU days) so
the field is not frozen, the brighter catalogue stars labelled with V, the
ephemeris as a grey line and earlier nights as orange dots.

Input: walk-stacks.npz (per-night noise-normalised medians, built by
walk-render.py on muppet) and walk-nights.csv (walk-summary.py).

    ~/astro/.venv/bin/python walk-render2.py    -> walk-anim2/NNNN.png (encode on muppet)
"""
import csv, os
from datetime import datetime

import numpy as np
import importlib.util
from scipy import ndimage as ndi
from PIL import Image, ImageDraw
from astropy.coordinates import SkyCoord, GCRS
from astropy.time import Time
import astropy.units as u

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("nep_find", f"{HERE}/nep-find.py")
_nf = importlib.util.module_from_spec(_s); _s.loader.exec_module(_nf)
OUT = f"{HERE}/walk-anim2"
RA0, DEC0, SCALE = 12.4, 2.4, 1.2 / 60     # as walk-render.py
UP = 2
MASK = (24, 16)                            # patch px: Saturn's glare plus its 15' E-W trail
TAU = 6.0                                  # days, rolling star stack (Saturn nights are 3-12 frames, so wider than Neptune's 4)
STEP = 2 / 3                               # days per animation frame
VLAB = 6.5                                 # label catalogue stars brighter than this


def day(iso):
    return datetime.fromisoformat(iso).timestamp() / 86400


def main():
    os.makedirs(OUT, exist_ok=True)
    z = np.load(f"{HERE}/walk-stacks.npz")
    A0 = z["stacks"].astype(np.float64); counts = z["counts"]
    rows = [r for r in csv.DictReader(open(f"{HERE}/walk-nights.csv")) if r["ok"] == "True"]
    n, h, w = A0.shape
    YY, XX = np.mgrid[0:h, 0:w]
    px = lambda ra, dec: _nf.to_px(ra, dec, RA0, DEC0, SCALE, w, h)
    pos = [px(float(r["ra"]), float(r["dec"])) for r in rows]
    eph = [px(float(r["eph_ra"]), float(r["eph_dec"])) for r in rows]
    dn = np.array([day(r["t_mid"]) for r in rows])
    ell = lambda x, y: np.hypot((XX - x) / MASK[0], (YY - y) / MASK[1])

    sigs = np.array([1.4826 * np.nanmedian(np.abs(a - np.nanmedian(a))) for a in A0])
    A = A0.copy()
    for k, (x, y) in enumerate(pos):                       # Saturn out of every night before combining
        A[k][ell(x, y) < 1] = np.nan
    ref = np.nanmedian(A / sigs[:, None, None], axis=0)
    star = ref > 6
    t = np.array([np.nanmedian(A[k][star] / ref[star]) for k in range(n)])
    t /= np.median(t)
    use = (t > 0.25) & (sigs / t < 4 * np.median(sigs / t))
    print("left out of the star stacks:", [r["night"] for r, u_ in zip(rows, use) if not u_])
    t = np.where(use, t, 1)
    As = A / t[:, None, None]; ss = sigs / t
    As[~use] = np.nan
    m = np.nanmedian(As, axis=0)
    good = np.isfinite(As) & (np.abs(As - m) < 4 * ss[:, None, None])
    base = np.where(good, (1 / ss ** 2)[:, None, None], 0.0)
    Az = np.nan_to_num(As)

    def combine(wn):
        Wk = base * wn[:, None, None]
        S = (Az * Wk).sum(0) / np.maximum(Wk.sum(0), 1e-12)
        S[Wk.sum(0) == 0] = 0
        return S

    deep = combine(np.ones(n))
    dsig = 1.4826 * np.median(np.abs(deep - np.median(deep)))

    hip = np.load(f"{HERE}/hip75.npy")
    c = SkyCoord(hip[:, 0] * u.deg, hip[:, 1] * u.deg).transform_to(GCRS(obstime=Time(datetime.fromisoformat(rows[n // 2]["t_mid"]))))
    labels = []
    for ra, dec, v in zip(c.ra.deg, c.dec.deg, hip[:, 2]):
        x, y = px(ra, dec)
        if v < VLAB and 2 < x < w - 2 and 2 < y < h - 2:
            labels.append((x * UP, y * UP, v))
    print("labelled:", sorted(round(float(v), 2) for *_, v in labels))

    def show(F):
        g = np.clip((F - 1.5 * dsig) / (18 * dsig), 0, 1) ** 0.6
        return Image.fromarray((g * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS).convert("RGB")

    keys = []
    for k, r in enumerate(rows):
        bg = combine(np.exp(-0.5 * ((dn - dn[k]) / TAU) ** 2))
        Sn = ndi.gaussian_filter(np.nan_to_num(A0[k] / t[k]), 1.0)
        mk = np.clip((1 - ell(*pos[k])) * 3, 0, 1)
        keys.append((dn[k], r["night"], bg * (1 - mk) + np.maximum(Sn, bg) * mk, pos[k], counts[k]))

    for f in os.listdir(OUT):
        os.remove(f"{OUT}/{f}")                # regenerated renders, not data
    T = np.arange(keys[0][0], keys[-1][0] + 1e-6, STEP)
    if T[-1] < keys[-1][0] - 1e-6:
        T = np.append(T, keys[-1][0])
    j = 0
    E = [(x * UP, y * UP) for x, y in eph]
    for i, tt in enumerate(T):
        while j < len(keys) - 2 and keys[j + 1][0] <= tt:
            j += 1
        (ta, na, Ia, pa, ca), (tb, nb, Ib, pb, cb) = keys[j], keys[j + 1]
        f = float(np.clip((tt - ta) / (tb - ta), 0, 1))
        im = show(Ia * (1 - f) + Ib * f)
        dr = ImageDraw.Draw(im)
        for x, y, v in labels:
            dr.text((x + 14, y - 16 if y > 24 else y + 6), f"V {v:.1f}", fill=(200, 170, 90))
        dr.line(E, fill=(70, 70, 80), width=1)
        for (td, _, _, (x, y), _) in keys:
            if td < tt - 1e-6:
                dr.ellipse((x * UP - 2, y * UP - 2, x * UP + 2, y * UP + 2), fill=(255, 170, 40))
        date = datetime.fromtimestamp(tt * 86400).strftime("%Y-%m-%d")
        near, cn = (na, ca) if f < 0.5 else (nb, cb)
        dr.text((10, 8), f"Saturn   {date}   eclipticam", fill=(230, 230, 230))
        if min(f, 1 - f) < 0.02:
            dr.text((10, 24), f"night {near}: {cn} x 60 s", fill=(140, 140, 147))
        else:
            dr.text((10, 24), f"between nights {na} and {nb} (cross-fade)", fill=(110, 110, 117))
        dr.text((10, h * UP - 20), f"stars: rolling stack of nearby nights ({TAU:.0f} d)   "
                f"orange: Saturn on earlier nights   grey: ephemeris", fill=(140, 140, 147))
        im.save(f"{OUT}/{i:04d}.png")
    print(f"{len(T)} frames, {STEP:.2f} d each")


if __name__ == "__main__":
    main()
