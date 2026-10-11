"""Is the split knot south of the Trapezium iota Ori + Struve 747, or deconvolution ringing?"""
import json, numpy as np
from scipy import ndimage as ndi
D = "/home/peter/astro/scratch/orion"
def hms(h,m,s): return 15*(h+m/60+s/3600)
def dms(d,m,s,sg=1): return sg*(abs(d)+m/60+s/3600)
cat = {"Betelgeuse":(hms(5,55,10.3),dms(7,24,25)),"Rigel":(hms(5,14,32.3),dms(8,12,6,-1)),
 "Bellatrix":(hms(5,25,7.9),dms(6,20,59)),"Saiph":(hms(5,47,45.4),dms(9,40,11,-1)),
 "Alnitak":(hms(5,40,45.5),dms(1,56,34,-1)),"Alnilam":(hms(5,36,12.8),dms(1,12,7,-1)),"Mintaka":(hms(5,32,0.4),dms(0,17,57,-1)),
 "mu Ori":(hms(6,2,23.0),dms(9,38,50)),"pi2 Ori":(hms(4,50,36.7),dms(8,54,1)),"pi3 Ori":(hms(4,49,50.4),dms(6,57,41))}
sword = {"iota Ori":(hms(5,35,25.986),dms(5,54,35.6,-1),2.77), "STF 747 AB":(0.678*hms(5,35,2.68)+0.322*hms(5,35,1.007), -(0.678*dms(6,0,7.3)+0.322*dms(6,0,33.4)), 4.30),   # WDS/SIMBAD: A HD 36960 V4.72, B HD 36959 V5.53; light-weighted centre
         "theta1 Ori C":(hms(5,35,16.46),dms(5,23,22.8,-1),5.13), "theta2 Ori A":(hms(5,35,22.9),dms(5,24,58,-1),5.02),
         "42 Ori":(hms(5,35,23.2),dms(4,50,18,-1),4.59), "45 Ori":(hms(5,35,39.5),dms(4,51,22,-1),5.26)}
rows = json.load(open(f"{D}/colour/colour-rows.json")); REF = 1791601980645
pix = {q["star"]: (q["x"], q["y"]) for q in rows if q["ep"] == REF}           # superpixels, 03:13 frame
ra0, de0 = np.radians(83.8), np.radians(-3.0)
def tan(ra, de):
    ra, de = np.radians(ra), np.radians(de); c = np.sin(de0)*np.sin(de)+np.cos(de0)*np.cos(de)*np.cos(ra-ra0)
    return np.array([np.cos(de)*np.sin(ra-ra0)/c, (np.cos(de0)*np.sin(de)-np.sin(de0)*np.cos(de)*np.cos(ra-ra0))/c])
def T(X): X = np.atleast_2d(X); x, y = X[:, 0], X[:, 1]; return np.column_stack([np.ones(len(x)), x, y, x*x, x*y, y*y])
names = [s for s in cat if s in pix]
X = np.array([tan(*cat[s]) for s in names]); Y = np.array([pix[s] for s in names])
C, *_ = np.linalg.lstsq(T(X), Y, rcond=None)
print(f"astrometric fit on {len(names)} stars, residual (superpixels): {np.round(np.hypot(*(T(X)@C - Y).T), 2)}")
cx, cy, h = 508, 526, 120                                     # deep grid: superpixel - (cx, cy) + h
pred = {s: T(tan(ra, de))[0] @ C - (cx - h, cy - h) for s, (ra, de, m) in sword.items()}
for s, p in pred.items(): print(f"  predicted {s:13s} grid ({p[0]:6.1f}, {p[1]:6.1f})  V {sword[s][2]}")
v = pred["STF 747 AB"] - pred["iota Ori"]
print(f"predicted iota -> STF 747: {np.hypot(*v):.2f} sp at {np.degrees(np.arctan2(v[1], v[0])):+.0f} deg (image x right, y down); "
      f"flux ratio ~{10**(-0.4*(4.30-2.77)):.2f}")
# measure: local maxima in the deconvolved deep stack (RL 30) and in one night (RL 30)
for name, f in [("deep RL30", f"{D}/deep/rl-deep-1s.npy"), ("10-09 RL30", f"{D}/deep/rl-10-09-1s.npy"), ("deep raw", f"{D}/deep/rl-deep-1s.npy")]:
    im = np.load(f)[0 if "raw" in name else 1]
    p = pred["iota Ori"]; x0, y0 = int(p[0]), int(p[1]); b = 10
    sub = im[y0-b:y0+b+1, x0-b:x0+b+1]
    mx = (sub == ndi.maximum_filter(sub, size=3)) & (sub > 0.08 * sub.max())
    pk = sorted([(sub[j, i], i + x0 - b, j + y0 - b) for j, i in zip(*np.nonzero(mx))], reverse=True)[:4]
    print(f"{name}: peaks near predicted iota Ori (value, x, y): " + "  ".join(f"({v_:.0f}, {x}, {y})" for v_, x, y in pk))
    if len(pk) > 1 and "raw" not in name:
        d = np.array(pk[1][1:]) - np.array(pk[0][1:])
        print(f"   second peak: {np.hypot(*d):.2f} sp at {np.degrees(np.arctan2(d[1], d[0])):+.0f} deg, ratio {pk[1][0]/pk[0][0]:.2f}")
json.dump({k: v.tolist() for k, v in pred.items()}, open("pred.json", "w"))
