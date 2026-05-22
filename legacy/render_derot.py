#!/usr/bin/env python3
"""Render the .npy accumulator from derot_stack with canvas extended
to show the off-frame pole."""
import argparse, os
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--pole-x", type=float, default=1919)
ap.add_argument("--pole-y", type=float, default=-218)
ap.add_argument("--downsample", type=int, default=2)
ap.add_argument("--target-median", type=int, default=50)
args = ap.parse_args()

acc = np.load(args.in_path)
H, W = acc.shape
med = float(np.median(acc.astype(np.float32)))
scale = args.target_median / max(1.0, med)
img8 = np.clip(acc.astype(np.float32) * scale, 0, 255).astype(np.uint8)
print(f"acc {W}x{H}  median={med:.1f}  scale={scale:.4f}")

px = args.pole_x / args.downsample
py = args.pole_y / args.downsample
ext_t = max(0, int(-py) + 80) if py < 0 else 0
ext_b = max(0, int(py - H) + 80) if py > H else 0
ext_l = max(0, int(-px) + 80) if px < 0 else 0
ext_r = max(0, int(px - W) + 80) if px > W else 0
ch, cw = H + ext_t + ext_b, W + ext_l + ext_r
canvas = np.zeros((ch, cw), dtype=np.uint8)
canvas[ext_t:ext_t+H, ext_l:ext_l+W] = img8
bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
pp = (int(px + ext_l), int(py + ext_t))
cv2.circle(bgr, pp, 30, (0, 255, 0), 2)
cv2.line(bgr, (pp[0]-60, pp[1]), (pp[0]+60, pp[1]), (0, 255, 0), 1)
cv2.line(bgr, (pp[0], pp[1]-60), (pp[0], pp[1]+60), (0, 255, 0), 1)
cv2.putText(bgr, f"pole ({args.pole_x:.0f}, {args.pole_y:.0f})",
            (pp[0]+40, pp[1]-20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out} ({cw}x{ch})")
