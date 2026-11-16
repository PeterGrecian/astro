#!/usr/bin/env python3
"""Polaris B, hqfs 2026-11-13: rotate the RDI residuals (rdi1113b.py) to north-up / east-left and stack.
North at A = toward the pole (circle fit to A's track); east = opposite to A's apparent motion (diurnal
motion is due west in the star's own frame), so handedness needs no assumption. Scale 2.13"/px.
B expected 18.2" (8.5 px) at PA ~230. Writes PNGs + numbers to ~/tmp/polarisb-b/."""
import os, numpy as np
from scipy import ndimage as ndi, optimize
from PIL import Image, ImageDraw
D = os.path.expanduser("~/tmp/polarisb-b")
Ds = np.load(f"{D}/Ds.npy"); T = np.load(f"{D}/track.npy")
t, ax, ay, s = T[:, 1], T[:, 2], T[:, 3], T[:, 4]
N = Ds.shape[1]; H = N // 2; SCALE = 2.13
# circle fit -> pole
def cres(p): return np.hypot(ax - p[0], ay - p[1]) - p[2]
xc, yc, R = optimize.least_squares(cres, [ax.mean(), ay.mean() + 800, 1000]).x
phi = np.unwrap(np.arctan2(ay - yc, ax - xc)); rate = np.polyfit((t - t[0]) / 3600, np.degrees(phi), 1)[0]
print(f"pole ({xc:.1f},{yc:.1f}) radius {R:.1f} px = {R*SCALE/3600:.4f} deg (Polaris ~0.63)  rot rate {rate:+.2f} deg/h (sidereal 15.04)  rms {np.std(cres([xc,yc,R])):.2f} px")
print(f"=> plate scale from radius if Polaris is 0.633 deg from pole: {0.633*3600/R:.3f} arcsec/px")
# per-frame north and east unit vectors (array coords)
vx, vy = np.gradient(ax, t), np.gradient(ay, t)
vx, vy = ndi.uniform_filter1d(vx, 41), ndi.uniform_filter1d(vy, 41)
nx, ny = xc - ax, yc - ay; nn = np.hypot(nx, ny); nx, ny = nx / nn, ny / nn
ex, ey = -vx, -vy; en = np.hypot(ex, ey); ex, ey = ex / en, ey / en
cross = nx * ey - ny * ex
print(f"handedness (n x e) sign: {np.sign(cross).mean():+.2f} (consistent if +-1)")
cols, rows = np.meshgrid(np.arange(N), np.arange(N))
E, Nn = H - cols, H - rows      # output: east left, north up
def stack(sel):
    acc = np.zeros((N, N)); w = np.zeros((N, N))
    for k in np.where(sel)[0]:
        X = H + E * ex[k] + Nn * nx[k]; Y = H + E * ey[k] + Nn * ny[k]
        d = Ds[k]; m = np.isfinite(d).astype(float); d = np.nan_to_num(d)
        acc += ndi.map_coordinates(d, [Y, X], order=1, cval=0); w += ndi.map_coordinates(m, [Y, X], order=1, cval=0)
    return np.where(w > 0.5 * w.max(), acc / np.maximum(w, 1e-9), np.nan), w
good = (np.abs(s - 8) < 1.0)
print(f"frames {len(t)}, scale-fit within 8+-1: {good.sum()}")
rr = np.hypot(cols - H, rows - H); pa = np.degrees(np.arctan2(-(E), Nn)) % 360   # PA from N through E
pa = np.degrees(np.arctan2(E, Nn)) % 360
def ringsub(S):
    out = S.copy()
    for r in range(N):
        m = (np.round(rr) == r) & np.isfinite(S)
        if m.sum() > 5: out[m] -= np.median(S[m])
    return out
def scan(S, r0=8.5, ap=2.5):
    res = []
    for p in range(0, 360, 5):
        cx, cy = H - r0 * np.sin(np.radians(p)), H - r0 * np.cos(np.radians(p))
        m = (np.hypot(cols - cx, rows - cy) < ap) & np.isfinite(S)
        res.append((p, np.nanmean(S[m]) if m.sum() > 3 else np.nan, m.sum()))
    return np.array(res)
def png(S, name, lo=None, hi=None, up=6):
    v = S.copy(); f = np.isfinite(v)
    lo = np.nanpercentile(v, 2) if lo is None else lo; hi = np.nanpercentile(v, 99.5) if hi is None else hi
    g = np.clip((v - lo) / (hi - lo), 0, 1); g[~f] = 0
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((N * up, N * up), Image.NEAREST).convert("RGB")
    a = np.array(im); a[np.repeat(np.repeat(~f, up, 0), up, 1)] = (60, 0, 0); im = Image.fromarray(a); d = ImageDraw.Draw(im)
    c = (H + 0.5) * up; r = 8.5 * up
    d.ellipse([c - r, c - r, c + r, c + r], outline=(0, 122, 255))
    bx, by = c - r * np.sin(np.radians(230)), c - r * np.cos(np.radians(230))
    d.ellipse([bx - 2.5 * up, by - 2.5 * up, bx + 2.5 * up, by + 2.5 * up], outline=(255, 149, 0))
    L = 10 / SCALE * up; d.line([10, N * up - 15, 10 + L, N * up - 15], fill=(255, 255, 255), width=3)
    d.text((10, N * up - 32), '10"', fill=(255, 255, 255))
    d.text((c - 4, 4), "N", fill=(255, 255, 255)); d.text((6, c - 6), "E", fill=(255, 255, 255))
    d.text((6, 6), name, fill=(142, 142, 147)); im.save(f"{D}/{name}.png")
for tag, sel in [("all", np.ones(len(t), bool)), ("good", good), ("early", good & (t < np.median(t))), ("late", good & (t >= np.median(t)))]:
    S, w = stack(sel); S2 = ringsub(S)
    np.save(f"{D}/S_{tag}.npy", S)
    sc = scan(S2); i = np.nanargmax(sc[:, 1]); noise = np.nanstd(sc[:, 1])
    at230 = sc[sc[:, 0] == 230][0][1]
    print(f"[{tag:5s}] n={sel.sum():4d}  ring r=8.5: peak PA {sc[i,0]:.0f} val {sc[i,1]:+.1f}  at PA230 {at230:+.1f}  ring rms {noise:.1f}  ({sc[i,1]/noise:.1f} sigma)")
    png(S2, f"ringsub_{tag}"); 
    if tag == "good": png(S, "stack_good")
    if tag == "good":
        for r0 in (6.5, 8.5, 10.5, 12.5):
            sc = scan(S2, r0); i = np.nanargmax(sc[:, 1]); print(f"   r={r0:4.1f}: peak PA {sc[i,0]:.0f} {sc[i,1]:+.1f} rms {np.nanstd(sc[:,1]):.1f} masked-frac {np.mean(sc[:,2]<4):.2f}")
# camera-frame (not derotated) control
C = np.load(f"{D}/nostack.npy"); C[~np.isfinite(C)] = np.nan; png(ringsub(C), "camera_frame_control")
# B's expected brightness: A flux from the 1.5 s reference scale -> rough; report saturation radius
print("sat-masked radius ~", np.sqrt(np.mean(np.isnan(Ds), axis=0).sum() / np.pi).round(1), "px (mean mask)")
