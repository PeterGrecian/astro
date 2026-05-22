#!/usr/bin/env python3
"""GIMP-recipe arc detector + walker + pole finder.

Pipeline (per peter@2026-05-21):
  1. Difference-of-Gaussians (r=1, r=2) — ridge enhancement
  2. Gaussian blur 4 px — smooth into continuous ridges
  3. Threshold 40 — binarise
  4. Walker: from each unclaimed bright pixel, BFS connected
     neighbours → one arc per BFS tree
  5. PCA per arc: midpoint + tangent direction
  6. Perpendicular at midpoint → passes through pole
  7. Pole = least-squares intersection of all perpendiculars
  8. Annotated diagnostic image

Operates on the raw .npy accumulator (full int64 dynamic range)
preferred; falls back to JPG if --in is .jpg.
"""
import argparse, os, sys
from collections import deque
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="in_path", required=True,
                help=".npy or .jpg of the photon sum")
ap.add_argument("--out", required=True)
ap.add_argument("--background", default=None,
                help="optional separate .jpg to draw annotations on; "
                     "default = the input (or stretched version of .npy)")
ap.add_argument("--dog-sigma1", type=float, default=1.0)
ap.add_argument("--dog-sigma2", type=float, default=2.0)
ap.add_argument("--blur-sigma", type=float, default=4.0)
ap.add_argument("--threshold", type=int, default=40)
ap.add_argument("--min-arc-pixels", type=int, default=40,
                help="reject arc components smaller than this")
ap.add_argument("--elongation-min", type=float, default=5.0)
args = ap.parse_args()

# 0. Load. .npy = raw accumulator; convert to 8-bit by stretching
#    sky-median to ~grey-50 so the GIMP recipe's threshold of 40 means
#    the same thing across runs.
if args.in_path.endswith(".npy"):
    raw = np.load(args.in_path)
    print(f"loaded {args.in_path} shape={raw.shape} dtype={raw.dtype}")
    med = float(np.median(raw))
    scale = 50.0 / max(1.0, med)
    img = np.clip(raw.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    print(f"stretched: median {med:.1f} → grey 50  scale={scale:.4f}")
else:
    img = cv2.imread(args.in_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"can't read {args.in_path}", file=sys.stderr); sys.exit(1)
    print(f"loaded {args.in_path} shape={img.shape}")
H, W = img.shape

# 1. DoG ridge enhancement
g1 = cv2.GaussianBlur(img, (0, 0), args.dog_sigma1)
g2 = cv2.GaussianBlur(img, (0, 0), args.dog_sigma2)
dog = cv2.subtract(g1, g2)  # bright on dark ridges
print(f"DoG: min={dog.min()} max={dog.max()} mean={dog.mean():.1f}")

# 2. Smoothing blur
blurred = cv2.GaussianBlur(dog, (0, 0), args.blur_sigma)
print(f"blurred: max={blurred.max()} mean={blurred.mean():.1f}")

# 3. Threshold
_, binary = cv2.threshold(blurred, args.threshold, 255, cv2.THRESH_BINARY)
n_bright = int((binary > 0).sum())
print(f"bright pixels at threshold={args.threshold}: {n_bright}")

# 4. Walker — BFS connected components. Faster: use opencv's CC.
n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
print(f"connected components: {n_cc - 1}")

# 5. Filter + PCA per arc
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
    # eigh returns ascending; flip to descending
    eigvals = eigvals[::-1]; eigvecs = eigvecs[:, ::-1]
    long_axis = eigvecs[:, 0]   # direction of the arc
    short_axis = eigvecs[:, 1]
    elong = eigvals[0] / max(eigvals[1], 1e-3)
    if elong < args.elongation_min:
        continue
    # Endpoints along the long axis
    projs = centred @ long_axis
    pmin = pts[np.argmin(projs)]
    pmax = pts[np.argmax(projs)]
    length = float(projs.max() - projs.min())
    arcs.append({
        "label": i, "n": area, "elong": elong,
        "centroid": centroid, "tangent": long_axis,
        "normal": short_axis, "p0": pmin, "p1": pmax,
        "length": length,
    })
print(f"surviving arcs (after elong + size filter): {len(arcs)}")

# 6. Each arc's perpendicular at midpoint passes through the pole.
#    Perpendicular line equation: (p - centroid) . tangent = 0
#    or equivalently: a*x + b*y = c where (a, b) = tangent and
#    c = tangent . centroid.
# 7. Solve least-squares for the pole minimising sum of squared
#    perpendicular distances to these lines, WEIGHTED by arc length
#    (longer arcs constrain better).
if len(arcs) >= 2:
    A = []
    b = []
    weights = []
    for a in arcs:
        tx, ty = a["tangent"]
        cx_, cy_ = a["centroid"]
        c = tx * cx_ + ty * cy_
        A.append([tx, ty])
        b.append(c)
        weights.append(a["length"])
    A = np.array(A); b = np.array(b)
    W_ = np.diag(np.array(weights))
    # Weighted least-squares: solve (A^T W A) x = A^T W b
    lhs = A.T @ W_ @ A
    rhs = A.T @ W_ @ b
    pole = np.linalg.solve(lhs, rhs)
    pole_cx, pole_cy = float(pole[0]), float(pole[1])
    # Per-arc residual: signed perpendicular distance from this pole
    # to each arc's tangent-line
    resids = []
    for a in arcs:
        tx, ty = a["tangent"]
        cx_, cy_ = a["centroid"]
        c = tx * cx_ + ty * cy_
        d = tx * pole_cx + ty * pole_cy - c
        resids.append(d)
    resids = np.array(resids)
    print(f"\nPole (weighted LS): cx={pole_cx:.1f}  cy={pole_cy:.1f}")
    print(f"  residual stats: median={np.median(resids):.2f} "
          f"std={resids.std():.2f}  max|.|={np.max(np.abs(resids)):.2f}")
    # Frame centre
    fcx, fcy = W/2, H/2
    dist_from_centre = np.sqrt((pole_cx - fcx)**2 + (pole_cy - fcy)**2)
    print(f"  distance from frame centre: {dist_from_centre:.0f} px")
    # If we assume 74 arcsec/px (rough), that's the angular distance
    # from zenith to the pole. = 90° - latitude.
    asec_per_px = 74.0
    angular = dist_from_centre * asec_per_px / 3600
    print(f"  → angular distance pole-to-zenith ≈ {angular:.1f}°")
    print(f"  → implied latitude            ≈ {90 - angular:.1f}°  (London 51.5°)")
else:
    pole_cx, pole_cy = -1, -1
    print("\nnot enough arcs for pole estimate")

# 8. Render diagnostic image
if args.background:
    bg = cv2.imread(args.background)
elif args.in_path.endswith(".jpg"):
    bg = cv2.imread(args.in_path)
else:
    bg = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
if bg.shape[:2] != (H, W):
    bg = cv2.resize(bg, (W, H))

# Extend canvas to make the off-frame pole visible
extend_top = max(0, int(-pole_cy) + 100) if pole_cy < 0 else 0
extend_bot = max(0, int(pole_cy - H) + 100) if pole_cy > H else 0
extend_left = max(0, int(-pole_cx) + 100) if pole_cx < 0 else 0
extend_right = max(0, int(pole_cx - W) + 100) if pole_cx > W else 0
ch = H + extend_top + extend_bot
cw = W + extend_left + extend_right
canvas = np.zeros((ch, cw, 3), dtype=np.uint8)
canvas[extend_top:extend_top+H, extend_left:extend_left+W] = bg

def to_canvas(p):
    return (int(p[0]) + extend_left, int(p[1]) + extend_top)

# Overlay arc pixels in red, then mark endpoints + tangents
bright_y, bright_x = np.where(binary > 0)
canvas[bright_y + extend_top, bright_x + extend_left] = (60, 60, 220)

for a in arcs:
    p0 = to_canvas(a["p0"]); p1 = to_canvas(a["p1"])
    mid = to_canvas(a["centroid"])
    cv2.circle(canvas, p0, 4, (50, 200, 255), -1)
    cv2.circle(canvas, p1, 4, (50, 200, 255), -1)
    # Extend the perpendicular bisector line from midpoint in direction
    # of normal (short axis) — toward the pole
    nx, ny = a["normal"]
    # Make the line cross the canvas
    L = ch + cw
    a_end = (int(a["centroid"][0] + nx*L), int(a["centroid"][1] + ny*L))
    b_end = (int(a["centroid"][0] - nx*L), int(a["centroid"][1] - ny*L))
    cv2.line(canvas, to_canvas(a_end), to_canvas(b_end),
             (180, 180, 180), 1, cv2.LINE_AA)

# Pole marker
if pole_cx > -1e6:
    pp = to_canvas((pole_cx, pole_cy))
    cv2.circle(canvas, pp, 30, (0, 255, 0), 3)
    cv2.line(canvas, (pp[0]-60, pp[1]), (pp[0]+60, pp[1]), (0, 255, 0), 2)
    cv2.line(canvas, (pp[0], pp[1]-60), (pp[0], pp[1]+60), (0, 255, 0), 2)
    cv2.putText(canvas, f"pole ({pole_cx:.0f}, {pole_cy:.0f})",
                (pp[0]+40, pp[1]-20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

cv2.imwrite(args.out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"\nwrote {args.out}  ({canvas.shape[1]}x{canvas.shape[0]})")
