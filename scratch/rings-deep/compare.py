"""Before/after of a deep driz2 with the camera-fixed ring map subtracted: same stretch on both, plus
old-minus-new (exactly what the ring map removed). Usage: compare.py <old fits> <new fits> <out prefix> <label>"""
import sys, numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw, ImageFont
old, new, out, lab = sys.argv[1:5]
A = fits.getdata(old, 0).astype(np.float32); B = fits.getdata(new, 0).astype(np.float32)
Wt = fits.getdata(new, 1) if len(fits.open(new)) > 1 else np.ones_like(B)
deep = (Wt > 0.5 * np.nanmax(Wt)) & np.isfinite(A) & np.isfinite(B)
def mad(v): return 1.4826 * np.median(np.abs(v - np.median(v)))
print(f"{lab}: old noise(MAD) {mad(A[deep]):.3f}  new {mad(B[deep]):.3f}  removed pattern rms {np.std((A - B)[deep]):.3f} ADU")
v = B[deep]; lo, hi = np.median(v) - 1.5 * mad(v), np.percentile(v, 99.7)
def g(S):
    x = np.clip((np.nan_to_num(S, nan=lo) - lo) / (hi - lo), 0, None); x = np.arcsinh(14 * x) / np.arcsinh(14)
    return (np.clip(x, 0, 1) * 255).astype(np.uint8)
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
D = A - B; s = 4 * np.std(D[deep]); dd = (np.clip((np.nan_to_num(D) + s) / (2 * s), 0, 1) * 255).astype(np.uint8)
for tag, im, t in (("before", g(A), f"{lab}: BEFORE (no ring map)"), ("after", g(B), f"{lab}: AFTER (ring map subtracted)"),
                   ("removed", dd, f"{lab}: what was removed (old - new, +-4 sigma)")):
    I = Image.fromarray(im).convert("RGB"); d = ImageDraw.Draw(I); d.rectangle([0, 0, I.width, 60], fill=(0, 0, 0)); d.text((20, 8), t, fill=(224, 224, 224), font=F)
    I.save(f"{out}-{tag}.jpg", quality=90)
    w = 1600; I.resize((w, round(I.height * w / I.width)), Image.LANCZOS).save(f"{out}-{tag}-web.jpg", quality=85)
