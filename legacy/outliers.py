import csv, numpy as np
rows = list(csv.DictReader(open("/home/peter/tmp/starcam-night/2026-05-20-21/brightness.csv")))
mean = np.array([float(r["mean"]) for r in rows])
W = 60
out_idx = []
for i in range(len(mean)):
    lo, hi = max(0, i - W//2), min(len(mean), i + W//2)
    seg = mean[lo:hi]
    m = np.median(seg)
    mad = np.median(np.abs(seg - m)) + 1e-6
    if abs(mean[i] - m) > 5.0 * mad:
        out_idx.append(i)
print(f"outliers: {len(out_idx)}")
for i in out_idx:
    r = rows[i]
    name = r["filename"].split("/")[-1]
    print(f"  {r['iso_utc'][:19]}  mean={r['mean']:>8s}  p95={r['p95']:>6s}  max={r['max']}  bright={r['bright_pixels']:>8s}  {name}")
