import os, sys, math
from datetime import timedelta
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import numpy as np
import check3
se = __import__("scan-epochs".replace("-", "_")) if False else None
import importlib.util
spec = importlib.util.spec_from_file_location("se", os.path.expanduser("~/astro/scratch/saturn-walk/scan-epochs.py"))
se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
for night in sys.argv[1:] or ["2026-06-12", "2026-06-20", "2026-07-05"]:
    fr = se.pick_frames(night)
    if not fr:
        print(night, "no frames"); continue
    t, p = fr[1] if len(fr) > 1 else fr[0]
    img, exp = se.load(p)
    try:
        q = check3.bootstrap(img, t + timedelta(seconds=exp / 2), dict(check3.P), night)
        print(f"SEED {night} az0 {math.degrees(q['az0']) % 360:.3f} alt0 {math.degrees(q['alt0']):.3f} "
              f"roll {math.degrees(q['roll']):.3f} f {q['f']:.1f}", flush=True)
    except SystemExit as e:
        print(night, "bootstrap failed:", e, flush=True)
