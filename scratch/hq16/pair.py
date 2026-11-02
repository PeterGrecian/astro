"""Side-by-side render of HQ16 frames (G, 2x2 binned then /2, per-frame 1-99.8% stretch),
with a caption per panel. Args: out.jpg frame..."""
import sys, numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw
out = sys.argv[1]; ps = []
for f in sys.argv[2:]:
    d = fits.getdata(f, 1).astype(np.float32) - 256
    g = (d[0::2,1::2] + d[1::2,0::2])
    g = g.reshape(760, 2, 1014, 2).mean((1, 3))
    lo, hi = np.percentile(g, [1, 99.8])
    im = Image.fromarray((np.clip((g-lo)/(hi-lo), 0, 1) ** 0.6 * 255).astype(np.uint8)).convert("RGB")
    ImageDraw.Draw(im).text((10, 10), f.split("/night/")[-1] if "/night/" in f else f, fill=(255, 80, 80))
    ps.append(np.asarray(im))
Image.fromarray(np.hstack(ps)).save(out, quality=88)
