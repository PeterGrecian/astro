#!/usr/bin/env python3
"""Before/after for the article www.petergrecian.co.uk/astro/project (mywebsite #1136 / idea #529):
astrocam night 2026-10-07, five derot-sky stacks all at --ref-utc 02:44:00 (identical geometry):
1, 3, 10, 30 min (mywebsite's m1..m30) and the whole night (mall). ONE stretch for all panels
(fixed ADU -> grey, set from the whole-night stack), so only the frame count differs.
Close-up: cell E3 of a 6x4 grid on the 2304x1296 frame (x 1536-1920, y 648-972) at 2x; wide: the frame.
Scale bar from f = 1683.86 px (binned, cammodel-2026-09-22): 1 deg = 29.39 px.
Writes ~/tmp/beforeafter/out/project-ba-{close,wide}-{1,3,10,30,night}.jpg and prints the noise table."""
import re, numpy as np
from pathlib import Path
from astropy.io import fits
from PIL import Image, ImageDraw, ImageFont
B = Path.home() / "tmp/beforeafter"; OUT = B / "out"; OUT.mkdir(exist_ok=True)
PXDEG = 1683.86 * np.pi / 180
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
SETS = [("1", "m1"), ("3", "m3"), ("10", "m10"), ("30", "m30"), ("night", "mall")]
def nframes(tag):
    m = re.search(r"(\d+) frames stacked", (B / f"{tag}.log").read_text()); return int(m.group(1))
def noise(tag):
    m = re.search(r"noise sigma ([\d.]+) ADU", (B / f"{tag}.log").read_text()); return float(m.group(1))
D = {k: fits.getdata(B / t / "derot-sky.fits", 0).astype(np.float32) for k, t in SETS}
Wt = fits.getdata(B / "mall/derot-sky.fits", 1)
good = (Wt > 0.3 * Wt.max()) & np.isfinite(D["night"])
LO, HI = np.percentile(D["night"][good], 5), np.percentile(D["night"][good], 99.8); GAIN = 12.0
print(f"stretch (all panels): lo {LO:.3f} hi {HI:.3f} ADU, asinh gain {GAIN}")
def grey(a):
    x = np.clip((np.nan_to_num(a, nan=LO) - LO) / (HI - LO), 0, None)
    return (np.clip(np.arcsinh(GAIN * x) / np.arcsinh(GAIN), 0, 1) * 255).astype(np.uint8)
def label(k):
    n = nframes(dict(SETS)[k])
    if k == "night": return f"whole night: {n} frames, {n} min (19:19-04:22 UTC)"
    return f"{k} min: {n} frame{'s' if n > 1 else ''}"
def bar(d, x, y, deg, s, text):
    L = deg * PXDEG * s; d.line([x, y, x + L, y], fill=(255, 255, 255), width=4); d.text((x, y - 34), text, fill=(255, 255, 255), font=FONT)
for k, t in SETS:
    g = grey(D[k]); n = nframes(t)
    c = Image.fromarray(g[648:972, 1536:1920]).resize((768, 648), Image.LANCZOS).convert("RGB"); d = ImageDraw.Draw(c)
    d.text((16, 12), label(k), fill=(224, 224, 224), font=FONT); bar(d, 16, 620, 2, 2, "2 deg")
    c.save(OUT / f"project-ba-close-{k}.jpg", quality=92)
    w = Image.fromarray(g).convert("RGB"); d = ImageDraw.Draw(w)
    d.text((20, 16), label(k), fill=(224, 224, 224), font=FONT); bar(d, 20, 1260, 10, 1, "10 deg")
    d.rectangle([1536, 648, 1920, 972], outline=(255, 149, 0), width=2)
    w.save(OUT / f"project-ba-wide-{k}.jpg", quality=90)
# noise: measured sigma vs 1/sqrt(N), and a two-part fit sigma^2 = a/N + c (c = what does not average down)
N = np.array([nframes(t) for _, t in SETS]); S = np.array([noise(t) for _, t in SETS])
A = np.c_[1 / N, np.ones_like(N, dtype=float)]; a, c = np.linalg.lstsq(A, S ** 2, rcond=None)[0]
print(" N   sigma   1/sqrt(N) pred   fit sqrt(a/N+c)")
for n, s in zip(N, S): print(f"{n:4d}  {s:.3f}   {S[0]/np.sqrt(n):.3f}          {np.sqrt(a/n+c):.3f}")
print(f"floor sqrt(c) = {np.sqrt(max(c,0)):.3f} ADU (does not average down); per-frame random sqrt(a) = {np.sqrt(a):.3f}")
