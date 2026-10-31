#!/usr/bin/env python3
"""Are the fshq detections stars? Remove fixed pattern, track objects between frames, show the brightest."""
import glob, os
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi

NIGHT = "/mnt/muppet/bigstore/xoverpi-frames/night/2026-10-30"
files = sorted(glob.glob(f"{NIGHT}/*/*.fits.fz"), key=lambda f: int(f.split("-")[-1].split(".")[0]))

def load(i):
    with fits.open(files[i]) as h:
        a = h[1].data.astype(np.float32)
    return (a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]) / 4

def ascii(c):
    ramp = " .:-=+*#%@"
    c = np.clip(c / max(c.max(), 1), 0, 1)
    return "\n".join("".join(ramp[int(v * 9)] for v in r) for r in c)

for start in (297, 5940, 10098):
    idx = list(range(start, start + 40))
    cube = np.array([load(i) for i in idx])
    fixed = np.median(cube, axis=0)          # stars drift out, hot pixels and pattern stay
    d = cube - fixed
    print(f"\n=== start {start}: fixed-pattern pixels >10 ADU above frame median: {(fixed - np.median(fixed) > 10).sum()}")
    tracks = []
    for k in range(len(idx)):
        sm = ndi.gaussian_filter(d[k], 1.5)
        s = 1.4826 * np.median(np.abs(sm[::3, ::3]))
        lab, n = ndi.label(sm > 6 * s)
        objs = []
        for j, sl in enumerate(ndi.find_objects(lab)):
            m = lab[sl] == j + 1
            if m.sum() < 6:
                continue
            f = (d[k][sl] * m).sum()
            cy, cx = ndi.center_of_mass(np.clip(d[k][sl], 0, None) * m)
            ys, xs = np.nonzero(m)
            objs.append((f, cx + sl[1].start, cy + sl[0].start, m.sum(), d[k][sl].max(), np.ptp(xs) + 1, np.ptp(ys) + 1))
        objs.sort(reverse=True)
        tracks.append(objs)
    print("objects per frame:", [len(t) for t in tracks])
    # frame-to-frame offset from pairwise differences of object positions
    dxs = []
    for a, b in zip(tracks[:-1], tracks[1:]):
        for oa in a[:10]:
            for ob in b[:10]:
                dxs.append((ob[1] - oa[1], ob[2] - oa[2]))
    if dxs:
        dxs = np.array(dxs)
        H, xe, ye = np.histogram2d(dxs[:, 0], dxs[:, 1], bins=[np.arange(-60, 61, 2)] * 2)
        ix, iy = np.unravel_index(H.argmax(), H.shape)
        vx, vy = xe[ix] + 1, ye[iy] + 1
        print(f"offset peak per frame (superpixels): dx {vx:.0f} dy {vy:.0f}, votes {H.max():.0f} of {len(tracks)-1} frame pairs")
    k = int(np.argmax([t[0][0] if t else 0 for t in tracks]))
    print("brightest frame in window", idx[k])
    for o in tracks[k][:6]:
        print(f"  flux {o[0]:.0f} x {o[1]:.0f} y {o[2]:.0f} npix {o[3]} peak {o[4]:.1f} extent {o[5]}x{o[6]}")
    for o in tracks[k][:2]:
        x, y = int(o[1]), int(o[2])
        c = ndi.gaussian_filter(d[k][max(y - 15, 0):y + 16, max(x - 24, 0):x + 25], 0.7)
        print(ascii(np.clip(c, 0, None)))
        print()
