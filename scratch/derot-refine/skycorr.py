"""Why is a night's glow sky mask degenerate? corr of each block with the median curve."""
import sys, numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
z = np.load(sys.argv[1]); t, cube = z["t"], z["cube"]
hh = np.array([(lambda d: d.hour + d.minute / 60)(datetime.fromtimestamp(x / 1000, timezone.utc).astimezone(ZoneInfo("Europe/London"))) for x in t])
use = (hh >= float(sys.argv[2])) | (hh < float(sys.argv[3]))
if "open" in z.files: use &= z["open"]
X = cube[:, :, 0] - 64; g = X[use, 1].reshape(use.sum(), -1); ref = np.median(g, 1)
corr = np.array([np.corrcoef(g[:, j], ref)[0, 1] for j in range(g.shape[1])])
print("frames", use.sum(), "ref min/med/max", np.percentile(ref, [0, 50, 100]).round(1), "ref dyn", round(ref.max() / ref.min(), 2))
print("corr pct 10/50/90", np.nanpercentile(corr, [10, 50, 90]).round(3))
lv = np.median(g, 0); print("above-black blocks", (lv > 0.18 * np.median(g)).sum())
