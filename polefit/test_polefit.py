#!/usr/bin/env python3
"""Regression test: polefit must reproduce the accepted answer on the samples.

Run:  python3 polefit/test_polefit.py
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from polefit import fit_pole  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def main():
    fails = 0
    for spec_path in sorted((HERE / "samples").glob("*.expected.json")):
        spec = json.loads(spec_path.read_text())
        img_path = spec_path.with_name(spec_path.name.replace(".expected.json", ".jpg"))
        if not img_path.exists():
            print(f"SKIP {img_path.name}: image missing")
            continue
        img = np.asarray(Image.open(img_path).convert("L"), dtype=np.float32)
        got = fit_pole(img, spec["plate_scale_deg_px"])
        exp = spec["expected"]
        if got is None:
            print(f"FAIL {img_path.name}: fit returned None (self-check rejected)")
            fails += 1
            continue
        d = np.hypot(got.x - exp["x"], got.y - exp["y"])
        ok = d <= exp["tolerance_px"]
        print(f"{'PASS' if ok else 'FAIL'} {img_path.name}: "
              f"({got.x:.1f},{got.y:.1f}) vs ({exp['x']},{exp['y']}) = {d:.1f} px  "
              f"r={got.radius_px:.1f}/{got.expected_radius_px:.1f} "
              f"sweep={got.sweep_deg:.0f} resid={got.residual_px:.2f} "
              f"stage1_shift={got.stage1_shift_px:.0f}")
        fails += (not ok)
    print(f"\n{'ALL PASS' if not fails else f'{fails} FAILURE(S)'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
