import csv, glob, os, numpy as np
root = "/mnt/bigstore/astro-data/astrocam-frames"
for bf in sorted(glob.glob(f"{root}/2026-*/brightness.csv"))[::4]:
    R = list(csv.DictReader(open(bf)))
    med = np.array([float(r["median"]) for r in R]); ex = [r.get("exptime", "?") for r in R]; print(list(R[0])[:14]) if "exptime" not in R[0] else None
    print(os.path.basename(os.path.dirname(bf)), len(R), "median min/p1/p50", med.min(), np.percentile(med, 1), np.median(med), "exp", sorted(set(ex))[:3])
