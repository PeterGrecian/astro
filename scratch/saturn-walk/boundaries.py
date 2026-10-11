#!/usr/bin/env python3
"""Step 2: before/after frames at each candidate eclipticam epoch boundary.

For each pair of nights, one frame near 23:00 UTC is binned to 2304x1296,
stretched, and halved to 1152x648. Writes the two frames (for blinking) and
a red/cyan overlay (before red, after cyan): a move shows as coloured fringes
on the roofline, a still camera as grey.

Run on muppet:  bigstore-run scratch/saturn-walk/boundaries.py
"""
import glob, os

import numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw

BASE = "/mnt/muppet/bigstore/eclipticam-frames/night"
OUT = os.path.expanduser("~/astro/scratch/saturn-walk/look/boundaries")
PAIRS = [
    ("00-control", "2026-07-14", "2026-08-12"),   # inside B2: what "no move" looks like
    ("01-june", "2026-06-21", "2026-06-24"),
    ("02-B1-B2", "2026-07-05", "2026-07-07"),
    ("03-B2-C", "2026-08-22", "2026-08-24"),
    ("04-C-D", "2026-08-24", "2026-08-28"),
    ("05-D-E", "2026-09-06", "2026-09-08"),
    ("06-E-F", "2026-09-13", "2026-09-15"),
    ("07-F-drift", "2026-09-15", "2026-09-24"),
    ("08-F-G", "2026-09-24", "2026-09-30"),
    ("09-G-1007", "2026-10-06", "2026-10-07"),
    ("10-1007-1009", "2026-10-07", "2026-10-09"),
]


def frame(night):
    for hh in ("23", "00", "22", "01"):
        fs = sorted(glob.glob(f"{BASE}/{night}/v3w/{hh}/*.fits.fz"))
        if fs:
            return fs[len(fs) // 2]
    raise FileNotFoundError(night)


def image(night):
    p = frame(night)
    with fits.open(p) as h:
        d = h[1].data.astype(np.float32)
    H, W = d.shape
    if W > 2304:
        d = d[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2).sum(axis=(1, 3))
    d = d[:1296 // 2 * 2, :2304].reshape(648, 2, 1152, 2).mean(axis=(1, 3))
    lo, hi = np.percentile(d, (1, 97))
    g = np.clip((d - lo) / (hi - lo), 0, 1) ** 0.6
    return (g * 255).astype(np.uint8), os.path.relpath(p, BASE)


def label(im, text):
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 8 * len(text) + 12, 20), fill=(0, 0, 0))
    dr.text((6, 4), text, fill=(255, 255, 0))
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    for tag, a, b in PAIRS:
        ia, pa = image(a)
        ib, pb = image(b)
        label(Image.fromarray(ia).convert("RGB"), f"{tag}  before {pa}").save(f"{OUT}/{tag}-a.jpg", quality=90)
        label(Image.fromarray(ib).convert("RGB"), f"{tag}  after {pb}").save(f"{OUT}/{tag}-b.jpg", quality=90)
        rgb = np.dstack([ia, ib, ib])
        label(Image.fromarray(rgb), f"{tag}  red {a}  cyan {b}").save(f"{OUT}/{tag}-c.jpg", quality=90)
        print(tag, pa, pb, flush=True)


if __name__ == "__main__":
    main()
