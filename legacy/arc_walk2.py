#!/usr/bin/env python3
"""Arc walker on an already-edge-detected binary-ish image.

Skips DoG; just thresholds + connects + PCAs.
"""
import argparse
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--background", required=True,
                help="image to draw annotations on (e.g. photon_dark50.jpg)")
ap.add_argument("--threshold", type=int, default=40)
ap.add_argument("--min-arc-pixels", type=int, default=80)
ap.add_argument("--elongation-min", type=float, default=5.0)
args = ap.parse_args()

img = cv2.imread(args.in_path, cv2.IMREAD_GRAYSCALE)
H, W = img.shape
print(f"loaded {args.in_path} {W}x{H}")

_, binary = cv2.threshold(img, args.threshold, 255, cv2.THRESH_BINARY)
print(f"bright pixels at threshold={args.threshold}: {int((binary>0).sum())}")

n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
print(f"connected components: {n_cc - 1}")

arcs = []
for i in range(1, n_cc):
    area = int(stats[i, cv2.CC_STAT_AREA])
    if area < args.min_arc_pixels:
        continue
    ys, xs = np.where(labels == i)
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centroid = pts.mean(axis=0)
    centred = pts - centroid
    cov = np.cov(centred.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    eigvals = eigvals[::-1]; eigvecs = eigvecs[:, ::-1]
    elong = eigvals[0] / max(eigvals[1], 1e-3)
    if elong < args.elongation_min:
        continue
    long_axis = eigvecs[:, 0]
    short_axis = eigvecs[:, 1]
    projs = centred @ long_axis
    p0 = pts[np.argmin(projs)]
    p1 = pts[np.argmax(projs)]
    length = float(projs.max() - projs.min())
    arcs.append({"n": area, "elong": elong, "centroid": centroid,
                 "tangent": long_axis, "normal": short_axis,
                 "p0": p0, "p1": p1, "length": length})

print(f"surviving arcs: {len(arcs)}")
for j, a in enumerate(sorted(arcs, key=lambda x: -x["length"])[:15]):
    print(f"  {j:3d}: n={a['n']:5d} elong={a['elong']:6.1f} "
          f"length={a['length']:.0f}  centroid=({a['centroid'][0]:.0f},{a['centroid'][1]:.0f})")

# Weighted LS for pole
if len(arcs) >= 2:
    A, b, w = [], [], []
    for a in arcs:
        tx, ty = a["tangent"]; cx_, cy_ = a["centroid"]
        A.append([tx, ty]); b.append(tx*cx_ + ty*cy_)
        w.append(a["length"])
    A = np.array(A); b = np.array(b); W_ = np.diag(w)
    lhs = A.T @ W_ @ A
    rhs = A.T @ W_ @ b
    pole = np.linalg.solve(lhs, rhs)
    pole_cx, pole_cy = float(pole[0]), float(pole[1])
    # Residuals
    resids = []
    for a in arcs:
        tx, ty = a["tangent"]; cx_, cy_ = a["centroid"]
        c = tx*cx_ + ty*cy_
        resids.append(tx*pole_cx + ty*pole_cy - c)
    resids = np.array(resids)
    print(f"\npole: ({pole_cx:.0f}, {pole_cy:.0f})")
    print(f"  residual: median={np.median(resids):.1f}  std={resids.std():.1f}  "
          f"max|.|={np.max(np.abs(resids)):.1f}")
    fcx, fcy = W/2, H/2
    dist = ((pole_cx-fcx)**2 + (pole_cy-fcy)**2)**0.5
    asec_per_px = 74.0
    ang = dist * asec_per_px / 3600
    print(f"  distance from frame centre: {dist:.0f} px = {ang:.1f}°")
    print(f"  → implied latitude: {90 - ang:.1f}°  (London = 51.5°)")
else:
    pole_cx = pole_cy = -1

# Render
bg = cv2.imread(args.background)
if bg.shape[:2] != (H, W):
    bg = cv2.resize(bg, (W, H))

extend_top    = max(0, int(-pole_cy) + 100) if pole_cy < 0 else 0
extend_bot    = max(0, int(pole_cy - H) + 100) if pole_cy > H else 0
extend_left   = max(0, int(-pole_cx) + 100) if pole_cx < 0 else 0
extend_right  = max(0, int(pole_cx - W) + 100) if pole_cx > W else 0
ch, cw = H + extend_top + extend_bot, W + extend_left + extend_right
canvas = np.zeros((ch, cw, 3), dtype=np.uint8)
canvas[extend_top:extend_top+H, extend_left:extend_left+W] = bg
def to_c(p): return (int(p[0]) + extend_left, int(p[1]) + extend_top)

# Tint arc pixels red
by, bx = np.where(binary > 0)
canvas[by + extend_top, bx + extend_left, 2] = np.clip(
    canvas[by + extend_top, bx + extend_left, 2].astype(int) + 120, 0, 255)

# Perpendicular bisector lines
for a in arcs:
    nx, ny = a["normal"]
    L = ch + cw
    e0 = (a["centroid"][0] + nx*L, a["centroid"][1] + ny*L)
    e1 = (a["centroid"][0] - nx*L, a["centroid"][1] - ny*L)
    cv2.line(canvas, to_c(e0), to_c(e1), (180, 180, 180), 1, cv2.LINE_AA)
    cv2.circle(canvas, to_c(a["p0"]), 4, (50, 200, 255), -1)
    cv2.circle(canvas, to_c(a["p1"]), 4, (50, 200, 255), -1)

if pole_cx > -1e6 and pole_cy > -1e6:
    pp = to_c((pole_cx, pole_cy))
    cv2.circle(canvas, pp, 40, (0, 255, 0), 3)
    cv2.line(canvas, (pp[0]-80, pp[1]), (pp[0]+80, pp[1]), (0, 255, 0), 2)
    cv2.line(canvas, (pp[0], pp[1]-80), (pp[0], pp[1]+80), (0, 255, 0), 2)
    cv2.putText(canvas, f"pole ({pole_cx:.0f}, {pole_cy:.0f})",
                (pp[0]+50, pp[1]-30),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"\nwrote {args.out}  ({cw}x{ch})")
