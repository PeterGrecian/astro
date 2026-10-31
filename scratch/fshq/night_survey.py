#!/usr/bin/env python3
"""fshq first night: sky level, star count and star shape, sampled through the night."""
import glob, os, sys
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
from PIL import Image

NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
OUT = os.path.expanduser("~/tmp/fshq-survey")
os.makedirs(OUT, exist_ok=True)
files = sorted(glob.glob(f"{NIGHT}/*/*.fits.fz"), key=lambda f: int(f.split("-")[-1].split(".")[0]))
print("frames", len(files))

def load(f):
    with fits.open(f) as h:
        return h[1].data.astype(np.float32), h[1].header

def bin2(a):
    h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
    a = a[:h, :w]
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4

def shape(im, x, y, r=12):
    """second moments of a cutout: long axis and short axis FWHM (superpixels), angle"""
    y0, y1, x0, x1 = max(y - r, 0), y + r + 1, max(x - r, 0), x + r + 1
    c = im[y0:y1, x0:x1]
    c = c - np.median(c)
    c = np.clip(c, 0, None)
    c[c < 0.15 * c.max()] = 0
    t = c.sum()
    if t <= 0:
        return None
    yy, xx = np.mgrid[:c.shape[0], :c.shape[1]]
    mx, my = (c * xx).sum() / t, (c * yy).sum() / t
    a, b, d = (c * (xx - mx) ** 2).sum() / t, (c * (yy - my) ** 2).sum() / t, (c * (xx - mx) * (yy - my)).sum() / t
    ev = np.linalg.eigvalsh([[a, d], [d, b]])
    return 2.355 * np.sqrt(max(ev[1], 0)), 2.355 * np.sqrt(max(ev[0], 0))

hdr_printed = False
print("idx file hour median mad npeaks n_sat maxadu fwhm_long fwhm_short bg_R bg_G bg_B")
step = max(len(files) // 50, 1)
best = (0, None)
rows = []
for i in range(0, len(files), step):
    f = files[i]
    raw, hdr = load(f)
    if not hdr_printed:
        print({k: hdr[k] for k in hdr if k in ("EXPTIME", "GAIN", "ANALOGUE", "BAYER", "CAMERA", "FOCUS", "RUNTAG", "DATE-OBS", "NAXIS1", "NAXIS2")}, raw.shape)
        hdr_printed = True
    R, G1, G2, B = raw[0::2, 0::2], raw[0::2, 1::2], raw[1::2, 0::2], raw[1::2, 1::2]
    im = bin2(raw)
    bg = ndi.median_filter(im[::4, ::4], 15)
    bg = ndi.zoom(bg, 4, order=1)[:im.shape[0], :im.shape[1]]
    d = im - bg
    sig = 1.4826 * np.median(np.abs(d[::3, ::3] - np.median(d[::3, ::3])))
    sm = ndi.gaussian_filter(d, 1.5)
    ssig = 1.4826 * np.median(np.abs(sm[::3, ::3] - np.median(sm[::3, ::3])))
    lab, n = ndi.label(sm > 6 * ssig)
    objs = ndi.find_objects(lab)
    sizes = ndi.sum(sm > 6 * ssig, lab, range(1, n + 1)) if n else []
    peaks = []
    for j, s in enumerate(objs):
        if sizes[j] < 4:
            continue
        pk = d[s].max()
        yy, xx = np.unravel_index(np.argmax(d[s]), d[s].shape)
        peaks.append((pk, s[1].start + xx, s[0].start + yy))
    peaks.sort(reverse=True)
    shp = [shape(d, x, y) for _, x, y in peaks[:15]]
    shp = [s for s in shp if s]
    fl = np.median([s[0] for s in shp]) if shp else 0
    fs = np.median([s[1] for s in shp]) if shp else 0
    if len(peaks) > best[0]:
        best = (len(peaks), f)
    print(i, os.path.basename(f)[-14:-8], f.split("/")[-2], f"{np.median(raw):.1f} {sig:.2f} {len(peaks)} {(raw >= 4090).sum()} {raw.max():.0f} {fl:.1f} {fs:.1f} {np.median(R):.1f} {np.median(G1):.1f} {np.median(B):.1f}", flush=True)
    rows.append((i, len(peaks)))

print("best", best)
# picture: stretched best frame, full and 400 px centre on its brightest star
raw, _ = load(best[1])
im = bin2(raw)
bg = ndi.median_filter(im[::4, ::4], 15)
d = im - ndi.zoom(bg, 4, order=1)[:im.shape[0], :im.shape[1]]
def stretch(a, hi):
    return (255 * np.clip(a / hi, 0, 1) ** 0.5).astype(np.uint8)
Image.fromarray(stretch(np.clip(d, 0, None), np.percentile(d, 99.9))).save(f"{OUT}/best_full.png")
sm = ndi.gaussian_filter(d, 1.5)
lab, n = ndi.label(sm > 6 * 1.4826 * np.median(np.abs(sm[::3, ::3])))
pk = sorted(((d[s].max(), s) for s in ndi.find_objects(lab)), key=lambda t: -t[0])[:12]
tiles = []
for v, s in pk:
    y, x = (s[0].start + s[0].stop) // 2, (s[1].start + s[1].stop) // 2
    c = d[max(y - 30, 0):y + 30, max(x - 30, 0):x + 30]
    t = np.zeros((60, 60), np.float32)
    t[:c.shape[0], :c.shape[1]] = c
    tiles.append(stretch(np.clip(t, 0, None), t.max() or 1))
while len(tiles) < 12:
    tiles.append(np.zeros((60, 60), np.uint8))
sheet = np.vstack([np.hstack(tiles[k:k + 4]) for k in (0, 4, 8)])
Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(f"{OUT}/best_stars.png")
print("saved", OUT)
