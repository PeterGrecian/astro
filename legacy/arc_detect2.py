#!/usr/bin/env python3
"""Stage-1 arc detection on the raw photon-sum .npy.

Reads the full-precision int64 accumulator instead of the stretched
JPG, so threshold logic is properly data-driven.
"""
import argparse, os, sys
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True,
                help=".npy file (int64 accumulator)")
ap.add_argument("--out", required=True)
ap.add_argument("--background-jpg", required=True,
                help="the stretched JPG to overlay annotations on")
ap.add_argument("--sky-y-frac", type=float, default=0.70,
                help="use top fraction of frame for sky-region stats")
ap.add_argument("--sky-x-frac", type=float, default=0.85,
                help="use left fraction of frame for sky-region stats")
ap.add_argument("--threshold-percentile", type=float, default=99.5)
ap.add_argument("--min-arc-pixels", type=int, default=30)
ap.add_argument("--elongation-min", type=float, default=4.0)
ap.add_argument("--residual-max", type=float, default=5.0)
ap.add_argument("--extend-up-frac", type=float, default=0.20)
args = ap.parse_args()

acc = np.load(args.in_path)
H, W = acc.shape
print(f"loaded {args.in_path}  shape={H}x{W}  dtype={acc.dtype}")

# Pick a threshold from the sky region (avoids the bright window-frame
# pulling the threshold up).
sky_y_end = int(H * args.sky_y_frac)
sky_x_end = int(W * args.sky_x_frac)
sky = acc[:sky_y_end, :sky_x_end]
thresh = int(np.percentile(sky, args.threshold_percentile))
print(f"threshold (sky p{args.threshold_percentile}): {thresh}")
print(f"sky median: {int(np.median(sky))}  sky max: {int(sky.max())}")

# Binarise full frame at that threshold
binary = (acc >= thresh).astype(np.uint8) * 255
# Light morph: close 1-pixel gaps, drop 1-pixel-wide noise
kernel = np.ones((3, 3), np.uint8)
binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
print(f"bright pixels after morph: {int((binary>0).sum())}")

# Connected components
n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
print(f"connected components: {n_cc - 1}")

# Filter + circle-fit
arcs = []
for i in range(1, n_cc):
    area = stats[i, cv2.CC_STAT_AREA]
    if area < args.min_arc_pixels:
        continue
    ys, xs = np.where(labels == i)
    pts = np.column_stack([xs, ys]).astype(np.float64)
    # PCA elongation
    cov = np.cov(pts.T)
    eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
    elong = eigvals[0] / max(eigvals[1], 1e-3)
    if elong < args.elongation_min:
        continue
    # Kasa fit
    x = pts[:, 0]; y = pts[:, 1]
    A = np.column_stack([x, y, np.ones(len(pts))])
    bvec = x*x + y*y
    sol, _, _, _ = np.linalg.lstsq(A, bvec, rcond=None)
    cx = sol[0]/2; cy = sol[1]/2
    r2 = sol[2] + cx*cx + cy*cy
    if r2 <= 0:
        continue
    r = np.sqrt(r2)
    dist = np.sqrt((x-cx)**2 + (y-cy)**2)
    residual = float(np.sqrt(np.mean((dist - r)**2)))
    if residual > args.residual_max:
        continue
    # Order points by angle from centre, sample 3 along the arc
    angles = np.arctan2(y - cy, x - cx)
    order = np.argsort(angles)
    pts_o = pts[order]
    n = len(pts_o)
    p_a = (int(pts_o[0, 0]), int(pts_o[0, 1]))
    p_m = (int(pts_o[n//2, 0]), int(pts_o[n//2, 1]))
    p_b = (int(pts_o[-1, 0]), int(pts_o[-1, 1]))
    arcs.append({
        "n": n, "elong": elong, "cx": cx, "cy": cy, "r": r,
        "residual": residual, "p_a": p_a, "p_m": p_m, "p_b": p_b,
    })

print(f"surviving arcs: {len(arcs)}")
arcs.sort(key=lambda a: -a["n"])

print()
print(f"{'idx':>3s} {'n':>5s} {'elong':>6s} {'cx':>8s} {'cy':>8s} {'r':>8s} {'resid':>6s}")
for j, a in enumerate(arcs):
    print(f"{j:3d} {a['n']:5d} {a['elong']:6.1f} {a['cx']:8.1f} {a['cy']:8.1f} {a['r']:8.1f} {a['residual']:6.2f}")

if arcs:
    cxs = np.array([a["cx"] for a in arcs])
    cys = np.array([a["cy"] for a in arcs])
    pole_cx = float(np.median(cxs))
    pole_cy = float(np.median(cys))
    print()
    print(f"pole estimate (median across {len(arcs)} arcs): "
          f"cx={pole_cx:.1f}  cy={pole_cy:.1f}")
    print(f"           IQR scatter: ±{float(np.percentile(cxs, 75) - np.percentile(cxs, 25)):.1f}, "
          f"±{float(np.percentile(cys, 75) - np.percentile(cys, 25)):.1f}")
else:
    pole_cx, pole_cy = -1, -1

# Render annotated diagnostic image.
bg = cv2.imread(args.background_jpg)
if bg is None:
    print(f"can't read {args.background_jpg}"); sys.exit(1)

extend_up = int(H * args.extend_up_frac)
# If pole is to the LOWER-LEFT (cy > H), extend downward instead.
# If pole is to the UPPER-RIGHT (cy < 0), extend upward.
# Decide from the data.
extend_y_top = 0
extend_y_bot = 0
extend_x_left = 0
extend_x_right = 0
if pole_cy >= 0:
    if pole_cy < 0:
        extend_y_top = -int(pole_cy) + 100
    elif pole_cy >= H:
        extend_y_bot = int(pole_cy - H) + 100
    if pole_cx < 0:
        extend_x_left = -int(pole_cx) + 100
    elif pole_cx >= W:
        extend_x_right = int(pole_cx - W) + 100

# Always pad upward by the user's extend-up-frac to make in-frame poles
# visible too.
extend_y_top = max(extend_y_top, int(H * args.extend_up_frac))

canvas_h = H + extend_y_top + extend_y_bot
canvas_w = W + extend_x_left + extend_x_right
canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
canvas[extend_y_top:extend_y_top+H, extend_x_left:extend_x_left+W] = bg

def to_canvas(p):
    return (int(p[0]) + extend_x_left, int(p[1]) + extend_y_top)

# Overlay arc pixels in red
red_pixels = np.where(binary > 0)
canvas[red_pixels[0] + extend_y_top, red_pixels[1] + extend_x_left] = (40, 40, 220)

# Sample points + lines toward each arc's individual centre
for a in arcs:
    for p in (a["p_a"], a["p_m"], a["p_b"]):
        cv2.circle(canvas, to_canvas(p), 6, (50, 200, 255), -1)
        pole = (a["cx"], a["cy"])
        dx = pole[0] - p[0]; dy = pole[1] - p[1]
        norm = np.sqrt(dx*dx + dy*dy)
        if norm < 1:
            continue
        ux, uy = dx/norm, dy/norm
        end = (int(p[0] + ux*4000), int(p[1] + uy*4000))
        cv2.line(canvas, to_canvas(p), to_canvas(end), (200, 200, 200), 1, cv2.LINE_AA)

# Consensus pole marker
if pole_cx > 0 or pole_cy > 0:
    pole_pt = to_canvas((pole_cx, pole_cy))
    cv2.circle(canvas, pole_pt, 30, (0, 255, 0), 2)
    cv2.line(canvas, (pole_pt[0]-50, pole_pt[1]),
             (pole_pt[0]+50, pole_pt[1]), (0, 255, 0), 1)
    cv2.line(canvas, (pole_pt[0], pole_pt[1]-50),
             (pole_pt[0], pole_pt[1]+50), (0, 255, 0), 1)
    cv2.putText(canvas, f"pole ({pole_cx:.0f}, {pole_cy:.0f})",
                (pole_pt[0]+40, pole_pt[1]-20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out}  canvas {canvas_h}x{canvas_w}")
