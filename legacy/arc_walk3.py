#!/usr/bin/env python3
"""Arc walker + iterative outlier rejection for pole estimate.

Walks arcs (as arc_walk2.py), but after the initial pole fit, drops
arcs whose perpendicular bisector misses the pole by > k×median
residual. Re-fits. Iterates until stable. Reports the refined pole.
"""
import argparse
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--background", required=True)
ap.add_argument("--threshold", type=int, default=40)
ap.add_argument("--min-arc-pixels", type=int, default=80)
ap.add_argument("--elongation-min", type=float, default=5.0)
ap.add_argument("--ignore-bottom-frac", type=float, default=0.30,
                help="reject arcs whose centroid is in the bottom N% of frame")
ap.add_argument("--ignore-right-frac", type=float, default=0.10,
                help="reject arcs whose centroid is in the right N% of frame")
ap.add_argument("--max-iter", type=int, default=10)
ap.add_argument("--reject-k", type=float, default=2.5,
                help="reject arcs whose residual > k × median residual")
args = ap.parse_args()

img = cv2.imread(args.in_path, cv2.IMREAD_GRAYSCALE)
H, W = img.shape
_, binary = cv2.threshold(img, args.threshold, 255, cv2.THRESH_BINARY)
n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)

arcs = []
y_cutoff = int(H * (1.0 - args.ignore_bottom_frac))
x_cutoff = int(W * (1.0 - args.ignore_right_frac))
for i in range(1, n_cc):
    area = int(stats[i, cv2.CC_STAT_AREA])
    if area < args.min_arc_pixels:
        continue
    ys, xs = np.where(labels == i)
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centroid = pts.mean(axis=0)
    # Pre-filter by location: drop bottom + right regions (window frame, light leak)
    if centroid[1] > y_cutoff or centroid[0] > x_cutoff:
        continue
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
                 "p0": p0, "p1": p1, "length": length, "kept": True})
print(f"after location/elong filter: {len(arcs)} arcs")


def fit_pole(arcs_kept):
    A, b, w = [], [], []
    for a in arcs_kept:
        tx, ty = a["tangent"]; cx_, cy_ = a["centroid"]
        A.append([tx, ty]); b.append(tx*cx_ + ty*cy_); w.append(a["length"])
    A = np.array(A); b = np.array(b); W_ = np.diag(w)
    lhs = A.T @ W_ @ A; rhs = A.T @ W_ @ b
    pole = np.linalg.solve(lhs, rhs)
    return float(pole[0]), float(pole[1])


def residuals(arcs_, pole_cx, pole_cy):
    out = []
    for a in arcs_:
        tx, ty = a["tangent"]; cx_, cy_ = a["centroid"]
        c = tx*cx_ + ty*cy_
        out.append(tx*pole_cx + ty*pole_cy - c)
    return np.array(out)


# Iterative reject
kept = list(arcs)
for it in range(args.max_iter):
    if len(kept) < 3:
        print(f"too few arcs ({len(kept)})"); break
    pcx, pcy = fit_pole(kept)
    res = residuals(kept, pcx, pcy)
    med_abs_res = float(np.median(np.abs(res)))
    cutoff = args.reject_k * med_abs_res
    new_kept = [a for a, r in zip(kept, res) if abs(r) <= cutoff]
    print(f"iter {it}: {len(kept)} arcs  pole=({pcx:.0f},{pcy:.0f})  "
          f"|res| median={med_abs_res:.1f}  cutoff={cutoff:.1f}  "
          f"keep={len(new_kept)}")
    if len(new_kept) == len(kept):
        break
    kept = new_kept

# Final pole
pole_cx, pole_cy = fit_pole(kept)
final_res = residuals(kept, pole_cx, pole_cy)
print(f"\nFINAL pole: ({pole_cx:.0f}, {pole_cy:.0f}) from {len(kept)} arcs")
print(f"  residuals: median={np.median(final_res):.1f}  std={final_res.std():.1f}  "
      f"max|.|={np.max(np.abs(final_res)):.1f}")

# Latitude back-out
fcx, fcy = W/2, H/2
dist = ((pole_cx-fcx)**2 + (pole_cy-fcy)**2)**0.5
# We DON'T know the pixel scale a priori. If we assume London 51.5° lat,
# then angle from zenith to pole = 38.5°. But camera is tilted, so the
# pole is not 38.5° from frame centre.
# Just report distance + scale options.
print(f"  distance frame-centre → pole: {dist:.0f} px")
for asec_pp in (74, 88, 100, 110):
    ang = dist * asec_pp / 3600
    print(f"    @ {asec_pp} arcsec/px → {ang:.1f}° from zenith (lat = {90-ang:.1f}°)")

# Render diagnostic
bg = cv2.imread(args.background)
if bg.shape[:2] != (H, W):
    bg = cv2.resize(bg, (W, H))
extend_top = max(0, int(-pole_cy) + 100) if pole_cy < 0 else 0
extend_bot = max(0, int(pole_cy - H) + 100) if pole_cy > H else 0
extend_left = max(0, int(-pole_cx) + 100) if pole_cx < 0 else 0
extend_right = max(0, int(pole_cx - W) + 100) if pole_cx > W else 0
ch, cw = H + extend_top + extend_bot, W + extend_left + extend_right
canvas = np.zeros((ch, cw, 3), dtype=np.uint8)
canvas[extend_top:extend_top+H, extend_left:extend_left+W] = bg
def to_c(p): return (int(p[0]) + extend_left, int(p[1]) + extend_top)

# Mark kept arcs in green, rejected arcs in dim red
kept_set = set(id(a) for a in kept)
for a in arcs:
    nx, ny = a["normal"]
    L = ch + cw
    e0 = (a["centroid"][0] + nx*L, a["centroid"][1] + ny*L)
    e1 = (a["centroid"][0] - nx*L, a["centroid"][1] - ny*L)
    if id(a) in kept_set:
        col = (180, 220, 180); thick = 1
    else:
        col = (60, 60, 120); thick = 1
    cv2.line(canvas, to_c(e0), to_c(e1), col, thick, cv2.LINE_AA)
    cv2.circle(canvas, to_c(a["p0"]), 4, (50, 200, 255), -1)
    cv2.circle(canvas, to_c(a["p1"]), 4, (50, 200, 255), -1)

# Pole marker
pp = to_c((pole_cx, pole_cy))
cv2.circle(canvas, pp, 40, (0, 255, 0), 3)
cv2.line(canvas, (pp[0]-80, pp[1]), (pp[0]+80, pp[1]), (0, 255, 0), 2)
cv2.line(canvas, (pp[0], pp[1]-80), (pp[0], pp[1]+80), (0, 255, 0), 2)
cv2.putText(canvas, f"pole ({pole_cx:.0f}, {pole_cy:.0f})  [{len(kept)}/{len(arcs)} arcs]",
            (pp[0]+50, pp[1]-30),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"\nwrote {args.out} ({cw}x{ch})")
