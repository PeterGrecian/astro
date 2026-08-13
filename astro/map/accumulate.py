#!/usr/bin/env python3
"""map-accumulate — scratch sidereal accumulation for ONE astrocam hour.

The smallest honest test of the map: does co-adding frames through a ROTATION
about the celestial pole actually sharpen stars, versus a plain sum?

Deliberately minimal. This is a scratch run (Peter, 2026-08-13) — it exists to
exercise the real operation on real data at low resolution, not to be the map.
What it does NOT do yet: drizzle (uses one bilinear resample, like detrans, so
we can measure whether that is the limiting factor), the stored vector field
(uses a geometric rotation about an assumed pole), CFA planes, buckets.

WHY A ROTATION, NOT A TRANSLATION. astrocam contains the celestial pole, so the
sky rotates in-frame: 15.041 deg/hour sidereal about the pole pixel. detrans's
uniform-translation model does not apply here — that is exactly why astrocam
needs the map.

THE TEST. Three stacks over the same frames:
  plain    straight sum, no motion compensation  -> stars trail
  derot    rotate each frame by -omega*(t-t0) about the pole, then sum
  single   one frame, for reference
If derot is right, its stars are TIGHTER than plain and brighter than single.
Measured by the 99.9th percentile (a proxy for peak sharpness: concentrated
flux pushes the bright tail up) and by star FWHM if a peak is isolable.

RUNS ON MUPPET (compute follows the data).
"""
import argparse
import glob
import os
import time
from datetime import datetime

import numpy as np
from astropy.io import fits

SIDEREAL_DEG_PER_S = 360.0 / 86164.0905      # 15.041 deg/hour


def read_frame(path, decimate):
    with fits.open(path, memmap=False) as hd:
        hdu = hd[1] if len(hd) > 1 else hd[0]
        arr = np.asarray(hdu.section[::decimate, ::decimate], dtype=np.float32)
        t = str(hdu.header.get("DATE-OBS", ""))
    return arr, t


def rotate_about(img, deg, cx, cy):
    """Rotate img by `deg` about (cx, cy). One bilinear resample.

    Bilinear on purpose for this scratch run: it matches what detrans already
    does, so if the map wins here it wins on GEOMETRY (rotation vs translation,
    measured pole) rather than on interpolation quality. Drizzle comes later
    and should improve on this, which is the next thing to measure.
    """
    from scipy.ndimage import affine_transform
    th = np.radians(deg)
    c, s = np.cos(th), np.sin(th)
    # inverse map: output -> input
    m = np.array([[c, s], [-s, c]], dtype=np.float64)
    centre = np.array([cy, cx], dtype=np.float64)
    offset = centre - m @ centre
    return affine_transform(img, m, offset=offset, order=1,
                            mode="constant", cval=0.0, output=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hour-dir", required=True)
    ap.add_argument("--decimate", type=int, default=4)
    ap.add_argument("--pole-x", type=float, default=None,
                    help="pole pixel x at FULL res (default: frame centre)")
    ap.add_argument("--pole-y", type=float, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=None, help="write FITS stacks here")
    args = ap.parse_args()

    fs = sorted(glob.glob(os.path.join(args.hour_dir, "*.fits.fz")))
    if args.limit:
        fs = fs[:args.limit]
    if len(fs) < 2:
        raise SystemExit("need >= 2 frames")
    print(f"{len(fs)} frames from {args.hour_dir}", flush=True)

    first, t0s = read_frame(fs[0], args.decimate)
    H, W = first.shape
    cx = (args.pole_x / args.decimate) if args.pole_x else (W - 1) / 2.0
    cy = (args.pole_y / args.decimate) if args.pole_y else (H - 1) / 2.0
    print(f"decimate {args.decimate} -> {W}x{H}, pole at ({cx:.1f}, {cy:.1f})"
          f"{' [ASSUMED frame centre — pole_prior_xy not used]' if not args.pole_x else ''}",
          flush=True)

    t0 = datetime.fromisoformat(t0s) if t0s else None
    plain = np.zeros((H, W), dtype=np.float64)
    derot = np.zeros((H, W), dtype=np.float64)
    n = 0
    tstart = time.time()
    for p in fs:
        img, ts = read_frame(p, args.decimate)
        if img.shape != (H, W):
            print(f"  skip {os.path.basename(p)}: shape {img.shape}")
            continue
        plain += img
        if t0 is not None and ts:
            dt = (datetime.fromisoformat(ts) - t0).total_seconds()
            derot += rotate_about(img, -SIDEREAL_DEG_PER_S * dt, cx, cy)
        else:
            derot += img
        n += 1
    dt_all = time.time() - tstart
    span = 0.0
    if t0 is not None:
        _, tl = read_frame(fs[-1], args.decimate)
        span = (datetime.fromisoformat(tl) - t0).total_seconds()
    print(f"stacked {n} frames in {dt_all:.1f}s "
          f"({dt_all/max(n,1)*1000:.0f} ms/frame); span {span/60:.1f} min "
          f"= {SIDEREAL_DEG_PER_S*span:.2f} deg of rotation", flush=True)

    def report(name, a):
        a = a / max(n, 1)
        med = float(np.median(a))
        p999 = float(np.percentile(a, 99.9))
        mx = float(a.max())
        print(f"  {name:8s} median {med:8.2f}  p99.9 {p999:9.2f}  max {mx:9.2f}"
              f"  contrast {(p999-med):8.2f}")
        return a

    print("\nstacks (per-frame mean):")
    pa = report("plain", plain)
    da = report("derot", derot)
    sa = report("single", first.astype(np.float64) * n)

    gain = (np.percentile(da, 99.9) - np.median(da)) / \
           max(np.percentile(pa, 99.9) - np.median(pa), 1e-6)
    print(f"\nderot/plain bright-tail contrast ratio: {gain:.3f}")
    print("  >1 means de-rotation concentrated the flux (stars tightened)")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        for name, a in (("plain", pa), ("derot", da), ("single", sa)):
            fits.writeto(os.path.join(args.out, f"{name}.fits"),
                         a.astype(np.float32), overwrite=True)
        print(f"wrote FITS to {args.out}")


if __name__ == "__main__":
    main()
