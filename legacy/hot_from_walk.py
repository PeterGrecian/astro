#!/usr/bin/env python3
"""Build a hot-pixel mask from the arc-walk image.

The arc-walk image has bright pixels at all frame-to-frame-changing
positions. Real stars produce long elongated streaks; hot pixels (read
noise around saturation) produce small isolated bright spots.

Filter the connected-components to keep only the SHORT, COMPACT ones
— those are the hot pixels.
"""
import argparse
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True,
                help="arc-walk image (the GIMP-recipe output)")
ap.add_argument("--out", required=True,
                help="hot-pixel mask as .npy (bool)")
ap.add_argument("--out-overlay", default=None,
                help="optional visualisation .jpg")
ap.add_argument("--threshold", type=int, default=40)
ap.add_argument("--max-arc-pixels", type=int, default=15,
                help="components smaller than this = hot pixels")
ap.add_argument("--max-elong", type=float, default=3.0,
                help="components less elongated than this = blob, not arc")
args = ap.parse_args()

img = cv2.imread(args.in_path, cv2.IMREAD_GRAYSCALE)
H, W = img.shape
print(f"loaded {args.in_path}  {W}x{H}")

_, binary = cv2.threshold(img, args.threshold, 255, cv2.THRESH_BINARY)
n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
print(f"connected components: {n_cc - 1}")

hot_mask = np.zeros((H, W), dtype=bool)
n_hot = 0
n_arc = 0
n_other = 0
for i in range(1, n_cc):
    area = int(stats[i, cv2.CC_STAT_AREA])
    if area > args.max_arc_pixels:
        n_arc += 1
        continue
    # Check elongation: too elongated = short arc, not a hot pixel
    ys, xs = np.where(labels == i)
    if len(xs) > 1:
        pts = np.column_stack([xs.astype(float), ys.astype(float)])
        cov = np.cov(pts.T)
        eigs = np.sort(np.linalg.eigvalsh(cov))[::-1]
        elong = eigs[0] / max(eigs[1], 1e-3)
        if elong > args.max_elong:
            n_other += 1
            continue
    # Mark these pixels (plus 1-pixel neighbourhood) as hot
    hot_mask[ys, xs] = True
    n_hot += 1

# Dilate slightly to catch charge-leak neighbours
hot_mask_d = cv2.dilate(hot_mask.astype(np.uint8), np.ones((3, 3), np.uint8),
                         iterations=1).astype(bool)
print(f"components classified:")
print(f"  hot (small + compact):    {n_hot}    ({int(hot_mask.sum())} px)")
print(f"  arcs (large):             {n_arc}")
print(f"  other (small but linear): {n_other}")
print(f"hot mask after 1px dilate:  {int(hot_mask_d.sum())} px")

np.save(args.out, hot_mask_d)
print(f"wrote {args.out}")

if args.out_overlay:
    bg = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    # Red on hot pixels
    bg[hot_mask_d] = (40, 40, 220)
    cv2.imwrite(args.out_overlay, bg, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"wrote {args.out_overlay}")
