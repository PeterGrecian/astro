"""Orion star colours (R/G, B/G per frame, raw Bayer planes) tracked through many 10-09 frames.

Each star is followed frame to frame from its probed position in the 03:13 frame. Per frame and
per plane: aperture = the star's trail (smoothed-G mask, dilated), sky = median of a ring around
it in the same plane. Pixels at the 10-bit ceiling are counted, so saturation is visible.
"""
import glob, os, json
import numpy as np
from astropy.io import fits
from scipy import ndimage as ndi
BASE = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data")
REF = 1791601980645
STARS = {"Betelgeuse": (810, 473), "Rigel": (1244, 1215), "Bellatrix": (1189, 618), "Saiph": (836, 1237),
         "Alnitak": (961, 922), "Alnilam": (1021, 902), "Mintaka": (1076, 872),
         "mu Ori": (714, 336), "pi2 Ori": (1573, 604), "pi3 Ori": (1568, 681)}   # A2 V, A1 V: astronomical white; F6 V: near-solar
files = sorted(glob.glob(f"{BASE}/eclipticam-frames/night/2026-10-09/v3w/*/*.fits.fz"), key=lambda p: int(os.path.basename(p)[:13]))
eps = [int(os.path.basename(p)[:13]) for p in files]; i0 = eps.index(REF)
SAT = 1023 - 64 - 5

def planes(p):
    h = fits.open(p)[1]; d = h.data.astype(np.float32) - h.header.get("BLACKLVL", 64)
    return {"R": d[0::2, 0::2], "G1": d[0::2, 1::2], "G2": d[1::2, 0::2], "B": d[1::2, 1::2]}, h.header["DATE-OBS"][11:16]

def measure(P, x, y, b=22):
    x, y = int(round(x)), int(round(y))
    if not (b <= x < P["R"].shape[1] - b and b <= y < P["R"].shape[0] - b): return None
    sl = np.s_[y - b:y + b, x - b:x + b]
    G = 0.5 * (P["G1"][sl] + P["G2"][sl]); g = G - np.median(G); sm = ndi.gaussian_filter(g, 1.0)
    nz = 1.4826 * np.median(np.abs(sm - np.median(sm)))
    lab, n = ndi.label(sm > 6 * nz)
    if n == 0: return None
    k = np.argmax(ndi.sum(sm, lab, np.arange(1, n + 1))) + 1
    core = lab == k; ap = ndi.binary_dilation(core, iterations=2)
    ring = ndi.binary_dilation(ap, iterations=7) & ~ndi.binary_dilation(ap, iterations=3)
    cy, cx = ndi.center_of_mass(np.clip(g, 0, None) * ap)
    out = {"x": x - b + cx, "y": y - b + cy, "npix": int(ap.sum())}
    for c in ("R", "G1", "G2", "B"):
        pl = P[c][sl]; sky = np.median(pl[ring]); out[c] = float((pl[ap] - sky).sum())
        out[c + "_sky"] = float(sky); out[c + "_sat"] = int((pl[ap] >= SAT).sum())
    out["G"] = 0.5 * (out["G1"] + out["G2"])
    return out

rows = []
for direction in (+1, -1):
    pos = {s: (X / 2, Y / 2) for s, (X, Y) in STARS.items()}; vel = {s: (0.0, 0.0) for s in STARS}
    i = i0 if direction == 1 else i0 - 1
    for step in range(30):
        P, utc = planes(files[i])
        for s in STARS:
            px, py = pos[s][0] + vel[s][0], pos[s][1] + vel[s][1]
            m = measure(P, px, py)
            if m is None: continue
            if step > 0 or direction == -1:
                vel[s] = (m["x"] - pos[s][0], m["y"] - pos[s][1]) if abs(m["x"] - px) < 8 else vel[s]
            pos[s] = (m["x"], m["y"]); m.update(star=s, utc=utc, ep=eps[i]); rows.append(m)
        i += direction
json.dump(rows, open("colour-rows.json", "w"))
print("wrote colour-rows.json", len(rows))
