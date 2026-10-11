#!/usr/bin/env python3
"""Neptune walking against the stars, from the whole-night stacks (nep/*.npz,
neptune.py / nep-restack.py) and the per-night measurements (nep-find.json,
nep-find.py).

Every night's stack is background-flattened, scaled to a common transparency
(slope against the median of all nights over the star pixels) and has its own
Neptune masked out. Then:

  - nep-deep.png: all nights, weights t^2/sigma^2, 4-sigma clip across nights.
  - the animation runs on an even clock (STEP days per frame). Its keyframes are
    the nights where Neptune was found (peak >= 4.5 sigma, < 4.5' from the
    ephemeris); each keyframe is a ROLLING star stack (the same weights times a
    Gaussian in time, sigma TAU days, so the field breathes with the season
    instead of sitting frozen) with that night's own Neptune laid in. Between
    keyframes the frames cross-fade in linear flux, before the stretch.

    ~/astro/.venv/bin/python nep-render.py      -> nep-anim/NNNN.png, nep-walk.mp4, nep-deep.png
"""
import json, os, subprocess
from datetime import datetime

import numpy as np
import importlib.util
from scipy import ndimage as ndi
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("nep_find", f"{HERE}/nep-find.py")
_nf = importlib.util.module_from_spec(_s); _s.loader.exec_module(_nf)
to_px = _nf.to_px
PLANET = os.environ.get("PLANET", "neptune")         # PLANET=uranus -> ura/, ura-find.json, ura-anim/, ura-walk.mp4
PRE = {"neptune": "nep", "uranus": "ura"}[PLANET]
NAME, VMAG_P, HIPF = {"neptune": ("Neptune", 7.8, "hip75.npy"), "uranus": ("Uranus", 5.7, "hip75-allsky.npy")}[PLANET]
D, OUT = f"{HERE}/{PRE}", f"{HERE}/{PRE}-anim"
UP = {"neptune": 4, "uranus": 6}[PLANET]
MASK = {"neptune": (11, 5), "uranus": (13, 6)}[PLANET]   # patch px: the 60 s trail runs ~15' east-west
VLAB = {"neptune": 99, "uranus": 6.3}[PLANET]       # label catalogue stars brighter than this (Taurus is crowded)
LO, HI = {"neptune": (1.0, 25), "uranus": (2.0, 150)}[PLANET]   # stretch, in deep-stack sigma: Uranus and its V 5 stars are 40-100 sigma
TAU = 4.0                                  # days, rolling star stack
STEP = {"neptune": 2 / 3, "uranus": 0.25}[PLANET]   # days per animation frame (Uranus: 18 days of data so far)
FPS = 24


def ell(x, y):
    return np.hypot((XX - x) / MASK[0], (YY - y) / MASK[1])


def flat(S, Wt):
    S = np.where(Wt > 0, S, np.nan)
    F = S - ndi.median_filter(np.nan_to_num(S, nan=np.nanmedian(S)), 41)
    sig = 1.4826 * np.nanmedian(np.abs(F - np.nanmedian(F)))
    return F, sig


def day(iso):
    return datetime.fromisoformat(iso).timestamp() / 86400


def main():
    global XX, YY
    os.makedirs(OUT, exist_ok=True)
    meas = {m["night"]: m for m in json.load(open(f"{HERE}/{PRE}-find.json"))}
    nights = sorted(meas)
    Fs, sigs = [], []
    for n in nights:
        z = np.load(f"{D}/{n}.npz")
        F, s = flat(z["stack"], z["weight"])
        Fs.append(F); sigs.append(s)
    raw = np.stack(Fs); A = raw.copy(); sigs = np.array(sigs)
    h, w = A.shape[1:]
    YY, XX = np.mgrid[0:h, 0:w]
    for k, n in enumerate(nights):                # Neptune out of every night before anything is combined
        A[k][ell(*meas[n]["pred"]) < 1] = np.nan
    ref = np.nanmedian(A / sigs[:, None, None], axis=0)
    star = ref > 6
    t = np.array([np.nanmedian(A[k][star] / ref[star]) for k in range(len(nights))])
    t /= np.median(t)
    # a night too cloudy to measure its own transparency adds nothing to the stars
    use = (t > 0.25) & (sigs / t < 4 * np.median(sigs / t))
    print("left out of the star stacks:", [n for n, u_ in zip(nights, use) if not u_])
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

    deep = combine(np.ones(len(nights)))
    cover = base.sum(0) > 0
    dsig = 1.4826 * np.median(np.abs(deep[cover]))
    print(f"{len(nights)} nights; deep sigma {dsig:.3g} vs best night {ss[use].min():.3g}")

    # the brighter stars, labelled with V so Neptune (V 7.8) has something to be compared with
    from astropy.coordinates import SkyCoord, GCRS
    from astropy.time import Time
    import astropy.units as u
    hip = np.load(f"{HERE}/{HIPF}")
    z0 = np.load(f"{D}/{nights[0]}.npz")
    c = SkyCoord(hip[:, 0] * u.deg, hip[:, 1] * u.deg).transform_to(GCRS(obstime=Time(meas[nights[len(nights) // 2]]["t"])))
    labels = []
    near = c.separation(SkyCoord(float(z0["ra0"]) * u.deg, float(z0["dec0"]) * u.deg, frame=c.frame)).deg < 10
    for ra, dec, v in zip(c.ra.deg[near], c.dec.deg[near], hip[near, 2]):   # far-side stars project into the patch too
        x, y = to_px(ra, dec, float(z0["ra0"]), float(z0["dec0"]), float(z0["scale"]), w, h)
        if v < VLAB and 2 < x < w - 2 and 2 < y < h + 2:
            labels.append((x * UP, y * UP, v))
    print("labelled:", [round(v, 2) for *_, v in labels])

    def show(F):
        g = np.clip((F - LO * dsig) / (HI * dsig), 0, 1) ** 0.5
        return Image.fromarray((g * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS).convert("RGB")

    def label(im):
        dr = ImageDraw.Draw(im)
        for x, y, v in labels:
            tx = x - 70 if x > w * UP - 80 else x + 30
            dr.text((tx, y - 22), f"V {v:.1f}", fill=(200, 170, 90))
        return dr

    im = show(deep); label(im); im.save(f"{HERE}/{PRE}-deep.png")

    # keyframes: rolling stars + that night's Neptune, in linear flux
    det = [n for n in nights if meas[n]["peak_sigma"] >= 4.5 and meas[n]["offset_arcmin"] < 4.5]
    dn = np.array([day(meas[n]["t"]) for n in nights])
    keys = []
    for n in det:
        k = nights.index(n)
        bg = combine(np.exp(-0.5 * ((dn - dn[k]) / TAU) ** 2))
        Fn = ndi.gaussian_filter(np.nan_to_num(raw[k] / t[k]), 0.8)
        cx, cy = meas[n]["meas"]
        mk = np.clip((1 - ell(cx, cy)) * 3, 0, 1)
        keys.append((dn[k], n, bg * (1 - mk) + np.maximum(Fn, bg) * mk, (cx, cy)))
    print(f"{len(det)} keyframe nights with Neptune found, of {len(nights)}")

    eph = [(meas[n]["pred"][0] * UP, meas[n]["pred"][1] * UP) for n in nights]
    for f in os.listdir(OUT):
        os.remove(f"{OUT}/{f}")                # regenerated renders, not data
    T = np.arange(keys[0][0], keys[-1][0] + 1e-6, STEP)
    if T[-1] < keys[-1][0] - 1e-6:
        T = np.append(T, keys[-1][0])          # end ON the last night
    j = 0
    for i, tt in enumerate(T):
        while j < len(keys) - 2 and keys[j + 1][0] <= tt:
            j += 1
        (ta, na, Ia, pa), (tb, nb, Ib, pb) = keys[j], keys[j + 1]
        f = float(np.clip((tt - ta) / (tb - ta), 0, 1))
        im = show(Ia * (1 - f) + Ib * f)
        dr = label(im)
        dr.line(eph, fill=(70, 70, 80), width=1)
        for (td, _, _, (px, py)) in keys:
            if td <= tt + 1e-6:
                dr.ellipse((px * UP - 2, py * UP - 2, px * UP + 2, py * UP + 2), fill=(60, 140, 255))
        cx, cy = (pa[0] * (1 - f) + pb[0] * f) * UP, (pa[1] * (1 - f) + pb[1] * f) * UP
        r = 4.5 * UP
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(60, 140, 255))
        date = datetime.fromtimestamp(tt * 86400).strftime("%Y-%m-%d")
        near, nf_ = (na, 1 - f) if f < 0.5 else (nb, f)
        dr.text((10, 8), f"{NAME} (V {VMAG_P})   {date}   eclipticam", fill=(230, 230, 230))
        if min(f, 1 - f) < 0.02:
            dr.text((10, 24), f"night {near}: {meas[near]['n']} x 60 s, {meas[near]['peak_sigma']:.1f} sigma, "
                    f"{meas[near]['offset_arcmin']:.1f}' from ephemeris", fill=(140, 140, 147))
        else:
            dr.text((10, 24), f"between nights {na} and {nb} (cross-fade)", fill=(110, 110, 117))
        dr.text((10, h * UP - 20), f"stars: rolling stack of nearby nights ({TAU:.0f} d)   "
                f"blue: {NAME} on earlier nights   grey: ephemeris", fill=(140, 140, 147))
        im.save(f"{OUT}/{i:04d}.png")
    print(f"{len(T)} frames, {STEP:.2f} d each, {len(T) / FPS:.0f} s at {FPS} fps")
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode:
        return                                 # no ffmpeg here: encode on muppet
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{OUT}/%04d.png",
                    "-vf", "tpad=stop_mode=clone:stop_duration=2,format=yuv420p", "-c:v", "libx264", "-crf", "18",
                    f"{HERE}/{PRE}-walk.mp4"], check=True)


if __name__ == "__main__":
    main()
