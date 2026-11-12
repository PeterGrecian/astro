"""Render one v3w frame (glow-subtracted, top-hat) with the 10-29 model's predicted bright stars circled."""
import sys, numpy as np
from importlib.machinery import SourceFileLoader
from scipy.ndimage import grey_opening
from PIL import Image, ImageDraw
ds = SourceFileLoader("ds", sys.argv[1]).load_module()
night, hh, cam, out = sys.argv[2:6]
gm = ds.GlowModel(f"/home/peter/eclipticam-frames/night/{night}/skyglow-model.npz")
cm = ds.CameraModel(cam)
dt, path = min(ds.night_frames(night), key=lambda tp: abs((tp[0] - ds.utc_on_night(night, hh)).total_seconds()))
raw = ds.load_binned(path)
img = gm.subtract(raw)
lo, hi = np.percentile(raw, [1, 99.7])
a = np.clip((raw - lo) / (hi - lo), 0, 1) ** 0.5
im = Image.fromarray((a * 255).astype(np.uint8)).convert("RGB")
x, y = cm.project(ds.star_enu(cm.p["stars_radec_j2000"], ds.mid(dt)))
d = ImageDraw.Draw(im)
for xi, yi in zip(x[:150], y[:150]):
    d.ellipse([xi - 8, yi - 8, xi + 8, yi + 8], outline=(0, 160, 255))
d.text((10, 10), f"{night} {path.split('/')[-1]} raw, 1-99.7%; circles = 10-29 model (first 150 catalogue stars)", fill=(255, 255, 0))
im.resize((im.width // 2, im.height // 2)).save(out, quality=85)
print(path, "raw med", np.median(raw))
