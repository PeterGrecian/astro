"""Why are the September nights soft? Star widths per night, interpolation blur, transform error."""
import glob, numpy as np
from scipy import ndimage as ndi
R = "/mnt/muppet/bigstore/eclipticam-frames/night"
def lum(z, suf=""): return z["R" + suf] + z["G" + suf] + z["B" + suf]
def flat(im): return im - ndi.median_filter(im, 41)
def noise(im): f = flat(im)[12:-12, 12:-12]; return 1.4826 * np.median(np.abs(f - np.median(f)))
def stars(im, k=10):
    f = flat(im); sm = ndi.gaussian_filter(f, 1.5); lab, n = ndi.label(sm > k * noise(im))
    idx = np.arange(1, n + 1); c = np.array(ndi.center_of_mass(np.clip(f, 0, None), lab, idx))[:, ::-1]
    fl = ndi.sum(f, lab, idx); o = np.argsort(-fl); return c[o][:40], fl[o][:40]
def widths(im, xy, r=6):
    """second-moment sigma along and across the trail for each star; median."""
    f = flat(im); out = []
    for x, y in xy:
        xi, yi = int(round(x)), int(round(y))
        if not (r < xi < f.shape[1] - r - 1 and r < yi < f.shape[0] - r - 1): continue
        c = np.clip(f[yi - r:yi + r + 1, xi - r:xi + r + 1], 0, None); c = np.where(c < 0.15 * c.max(), 0, c)
        q, p = np.mgrid[-r:r + 1, -r:r + 1]; w = c.sum(); mx, my = (c * p).sum() / w, (c * q).sum() / w
        I = np.array([[(c * (p - mx) ** 2).sum(), (c * (p - mx) * (q - my)).sum()], [(c * (p - mx) * (q - my)).sum(), (c * (q - my) ** 2).sum()]]) / w
        ev = np.linalg.eigvalsh(I); out.append(np.sqrt(ev[::-1]))
    return np.median(np.array(out), 0)
ref = lum(np.load(f"{R}/2026-10-09/sword-stack-w.npz", allow_pickle=True)); sr, fr = stars(ref, 15)
print("night       frames  along  across   (sigma, superpixels; bright stars of each night's own stack)")
for f in sorted(glob.glob(f"{R}/*/sword-stack-w.npz")):
    z = np.load(f, allow_pickle=True); L = lum(z); s, _ = stars(L, 15)
    a, c = widths(L, s[:15]); print(f"{f.split('/')[-2]}  {int(z['n']):4d}   {a:.2f}   {c:.2f}")
# interpolation blur: shift 10-09 by half a superpixel and back, bilinear vs cubic
for order in (1, 3):
    sh = ndi.shift(ndi.shift(ref, (0.5, 0.5), order=order), (-0.5, -0.5), order=order)
    one = ndi.shift(ref, (0.5, 0.5), order=order)
    print(f"order {order}: one half-pixel resample widths {widths(one, sr[:15] + 0.5)}  vs original {widths(ref, sr[:15])}")
