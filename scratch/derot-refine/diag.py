"""Diagnose derot-sky refine's coarse match on one v3w night (run on muppet, tree copy)."""
import sys, importlib.util, numpy as np
from importlib.machinery import SourceFileLoader
from scipy.ndimage import maximum_filter, grey_opening
ds = SourceFileLoader("ds", sys.argv[1]).load_module()
night, hh, cam, good = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None
gm = ds.GlowModel(f"/home/peter/eclipticam-frames/night/{night}/skyglow-model.npz")
cm = ds.CameraModel(cam)
t = ds.utc_on_night(night, hh)
dt, path = min(ds.night_frames(night), key=lambda tp: abs((tp[0] - t).total_seconds()))
raw = ds.load_binned(path); img = gm.subtract(raw)
print(path, img.shape, "nan", np.isnan(img).sum(), "raw med", np.nanmedian(raw))
sky = gm.sky_mask(img.shape, 2); print("sky px", sky.sum())
th = img - grey_opening(img, size=(5, 5)); th[~sky] = 0
print("th sky med/MAD", np.median(th[sky]), np.median(np.abs(th[sky] - np.median(th[sky]))))
V = ds.star_enu(cm.p["stars_radec_j2000"], ds.mid(dt))
for name, p in [("model", cm.p)] + ([("good", ds.CameraModel(good).p)] if good else []):
    x, y = ds.CameraModel(p).project(V)
    H, W = img.shape
    ok = (x > 5) & (x < W - 5) & (y > 5) & (y < H - 5)
    xi, yi = np.round(x[ok]).astype(int), np.round(y[ok]).astype(int)
    print(name, "in frame", ok.sum(), "on sky", sky[yi, xi].sum(),
          "th/tn at stars: pct50/90", np.percentile(th[yi, xi], [50, 90]))
