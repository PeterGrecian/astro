#!/usr/bin/env python3
"""Stage-1 arc detection on the photon-summed image.

Pipeline:
  1. Load the photon-sum (grayscale). Apply a high-pass filter
     (subtract a heavy gaussian blur of itself) to suppress the
     column-banding background.
  2. Threshold to get bright pixels.
  3. Connected components → one component per arc candidate.
  4. For each component: skeletonise, get an ordered point list.
  5. Reject non-elongated blobs (PCA eigenvalue ratio) and very
     short components.
  6. Algebraic circle fit (Kasa method) to all points on each
     arc → (cx, cy, r).
  7. Render annotated image: arcs in red, 3 sample points per arc
     in bright yellow, perpendicular bisectors extended toward
     the inferred pole. Canvas extended 20% upward to show the
     pole.
  8. Print per-arc (cx, cy, r) table.

Run on photon_dark50.jpg.
"""
import argparse, os, sys
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--min-arc-pixels", type=int, default=30)
ap.add_argument("--elongation-min", type=float, default=4.0,
                help="PCA eigenvalue ratio threshold (long/short)")
ap.add_argument("--extend-up-frac", type=float, default=0.20)
args = ap.parse_args()

# 1. Load
img = cv2.imread(args.in_path, cv2.IMREAD_GRAYSCALE)
if img is None:
    print(f"can't read {args.in_path}", file=sys.stderr); sys.exit(1)
H, W = img.shape
print(f"loaded {args.in_path}  shape={H}x{W}")

# 2. High-pass: subtract a heavy gaussian to remove the slow gradient
#    background (cloud-glow, column banding).
blur = cv2.GaussianBlur(img, (51, 51), 25)
hp = cv2.subtract(img, blur)
print(f"hp: max={hp.max()} mean={hp.mean():.1f}")

# 3. Threshold. Pick a value that catches the arcs but not the noise.
#    The mode of the hp image is ~0 (background); arcs are >10.
thresh_val = max(5, int(hp.mean() + 3 * hp.std()))
print(f"threshold: {thresh_val}")
_, binary = cv2.threshold(hp, thresh_val, 255, cv2.THRESH_BINARY)

# Small closing to fill gappy arcs (caused by skip-frames in the
# accumulator); small opening to drop single-pixel noise.
kernel = np.ones((3, 3), np.uint8)
binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
print(f"binary: bright pixels = {int((binary>0).sum())}")

# 4. Connected components
n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
print(f"connected components: {n_cc - 1}")

# 5. Per-component: filter + circle-fit
arcs = []  # list of dicts: {'points': [(y,x)...], 'cx', 'cy', 'r', 'mid', 'tangent'}
for i in range(1, n_cc):
    area = stats[i, cv2.CC_STAT_AREA]
    if area < args.min_arc_pixels:
        continue
    ys, xs = np.where(labels == i)
    pts = np.column_stack([xs, ys]).astype(np.float64)  # (x, y) order
    # PCA elongation
    cov = np.cov(pts.T)
    eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
    elong = eigvals[0] / max(eigvals[1], 1e-3)
    if elong < args.elongation_min:
        continue

    # Kasa circle fit: (x-cx)^2 + (y-cy)^2 = r^2
    # Linear in (a, b, c) where a=2*cx, b=2*cy, c=r^2 - cx^2 - cy^2
    # x^2 + y^2 = a*x + b*y + c
    x = pts[:, 0]; y = pts[:, 1]
    A = np.column_stack([x, y, np.ones(len(pts))])
    bvec = x*x + y*y
    sol, _, _, _ = np.linalg.lstsq(A, bvec, rcond=None)
    cx = sol[0] / 2
    cy = sol[1] / 2
    r2 = sol[2] + cx*cx + cy*cy
    if r2 <= 0:
        continue
    r = np.sqrt(r2)

    # Residual: how well does the fit match? Drop bad fits.
    dist = np.sqrt((x-cx)**2 + (y-cy)**2)
    residual_rms = np.sqrt(np.mean((dist - r)**2))
    if residual_rms > 5.0:   # >5 px scatter from a circle means it's not a circle
        continue

    # Sample 3 points along the arc for the perpendicular-bisector
    # rendering: endpoints + midpoint by angular position around (cx, cy)
    angles = np.arctan2(y - cy, x - cx)
    order = np.argsort(angles)
    if order[0] != 0:
        pts = pts[order]
        x = pts[:, 0]; y = pts[:, 1]
        angles = angles[order]
    p_a = (int(x[0]), int(y[0]))
    p_m = (int(x[len(pts)//2]), int(y[len(pts)//2]))
    p_b = (int(x[-1]), int(y[-1]))

    arcs.append({
        "n_points": len(pts), "elong": elong,
        "cx": cx, "cy": cy, "r": r, "residual": residual_rms,
        "p_a": p_a, "p_m": p_m, "p_b": p_b,
    })

print(f"surviving arcs: {len(arcs)}")
arcs.sort(key=lambda a: -a["n_points"])  # longest first

# 6. Print per-arc table
print()
print(f"{'idx':>3s} {'n':>5s} {'elong':>6s} {'cx':>8s} {'cy':>8s} {'r':>8s} {'resid':>6s}")
for j, a in enumerate(arcs):
    print(f"{j:3d} {a['n_points']:5d} {a['elong']:6.1f} {a['cx']:8.1f} {a['cy']:8.1f} {a['r']:8.1f} {a['residual']:6.2f}")

# Median of (cx, cy) across the surviving arcs — rough pole estimate
if arcs:
    cxs = np.array([a["cx"] for a in arcs])
    cys = np.array([a["cy"] for a in arcs])
    pole_cx = float(np.median(cxs))
    pole_cy = float(np.median(cys))
    cx_iqr = float(np.percentile(cxs, 75) - np.percentile(cxs, 25))
    cy_iqr = float(np.percentile(cys, 75) - np.percentile(cys, 25))
    print()
    print(f"pole estimate (median): cx={pole_cx:.1f}  cy={pole_cy:.1f}")
    print(f"           IQR scatter: ±{cx_iqr:.1f}, ±{cy_iqr:.1f}")
else:
    pole_cx, pole_cy = -1, -1
    print("no arcs detected — can't estimate pole")

# 7. Render the diagnostic image. Extend canvas 20% upward.
extend = int(H * args.extend_up_frac)
canvas_h = H + extend
canvas_w = W
canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
# Original image at the bottom of the extended canvas
canvas[extend:, :, :] = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

# Helper: image coords → canvas coords (shift y by `extend`)
def to_canvas(p):
    return (int(p[0]), int(p[1]) + extend)

# Draw each arc's skeleton in red, plus its 3 sample points, plus
# a perpendicular bisector line from each sample point toward the pole.
for a in arcs:
    # Draw the original component pixels in red
    mask = labels == 0  # zero mask placeholder; replaced below
    # Get the component's binary mask from `labels`
    # We didn't keep the per-arc label id — refit by index.
# Re-find labels for the surviving arcs (cheap):
for a in arcs:
    # locate by (cx, cy) approximate match in stats
    pass
# Simpler: redraw red over the entire binary (all bright pixels)
red_mask = (binary > 0)
canvas[extend:, :, :][red_mask] = (40, 40, 220)  # red-ish

# Now overlay the per-arc highlights
for a in arcs:
    for p in (a["p_a"], a["p_m"], a["p_b"]):
        cv2.circle(canvas, to_canvas(p), 6, (50, 200, 255), -1)  # yellow
        # Perpendicular line from this point toward the pole (cx, cy).
        # The line direction from p to pole is (pole - p); draw a line
        # the full length so the intersection is visible.
        pole = (a["cx"], a["cy"])
        dx = pole[0] - p[0]; dy = pole[1] - p[1]
        norm = np.sqrt(dx*dx + dy*dy)
        if norm < 1: continue
        # Extend each line full canvas length toward (cx, cy)
        ux, uy = dx / norm, dy / norm
        end_p = (int(p[0] + ux * 4000), int(p[1] + uy * 4000))
        cv2.line(canvas, to_canvas(p), to_canvas(end_p),
                 (200, 200, 200), 1, cv2.LINE_AA)

# Mark the consensus pole if we have one
if pole_cx > 0:
    pole_pt = to_canvas((pole_cx, pole_cy))
    # Big circle + crosshair
    cv2.circle(canvas, pole_pt, 30, (0, 255, 0), 2)
    cv2.line(canvas, (pole_pt[0]-50, pole_pt[1]),
                     (pole_pt[0]+50, pole_pt[1]), (0, 255, 0), 1)
    cv2.line(canvas, (pole_pt[0], pole_pt[1]-50),
                     (pole_pt[0], pole_pt[1]+50), (0, 255, 0), 1)
    cv2.putText(canvas, f"pole ({pole_cx:.0f}, {pole_cy:.0f})",
                (pole_pt[0]+40, pole_pt[1]-20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"wrote {args.out}")
