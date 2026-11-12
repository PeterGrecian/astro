"""Is the v3w 'pointing drift' a clock error? Fixed camera model, slide the frame time."""
import sys, numpy as np
from datetime import timedelta
from importlib.machinery import SourceFileLoader
from scipy.ndimage import maximum_filter, grey_opening
ds = SourceFileLoader("ds", sys.argv[1]).load_module()
night, hh, cam = sys.argv[2], sys.argv[3], sys.argv[4]
gm = ds.GlowModel(f"/home/peter/eclipticam-frames/night/{night}/skyglow-model.npz")
cm = ds.CameraModel(cam)
t = ds.utc_on_night(night, hh)
dt, path = min(ds.night_frames(night), key=lambda tp: abs((tp[0] - t).total_seconds()))
img = gm.subtract(ds.load_binned(path)); H, W = img.shape
th = img - grey_opening(img, size=(5, 5))
tn = 1.4826 * np.median(np.abs(th - np.median(th)))
pk = (th == maximum_filter(th, size=5)) & (th > np.median(th) + 6 * tn)
sm = maximum_filter(pk, size=5)
res = []
for off in range(-60, 61):
    x, y = cm.project(ds.star_enu(cm.p["stars_radec_j2000"], ds.mid(dt) + timedelta(minutes=off)))
    ok = (x > 3) & (x < W - 3) & (y > 3) & (y < H - 3)
    res.append((sm[np.round(y[ok]).astype(int), np.round(x[ok]).astype(int)].sum(), off))
res.sort(reverse=True)
print(night, path.split("/")[-1], "peaks", pk.sum(), "best (score, min):", res[:4], "at 0:", [r for r in res if r[1] == 0])
