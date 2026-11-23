"""Are dark hours clear / cloudy / mixed, and in what proportion?
Per sampled frame (one per 10 min): star count / its regime's reference (hours.csv regime_ref_stars).
Dark = sun < -18. Moon up kept separate (it cuts star counts without cloud).
Hour class: clear if every frame >= HI, cloudy if every frame < LO, else mixed.
Usage: classes.py <survey dir> <out png>"""
import sys, csv, datetime, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sdir, png = sys.argv[1], sys.argv[2]; LO, HI = 0.25, 0.6
H = {r["hour"]: r for r in csv.DictReader(open(f"{sdir}/hours.csv"))}
fr = {"moonless": [], "moon up": []}; hrs = {"moonless": {}, "moon up": {}}
for night in sorted({r["night"] for r in H.values()}):
    try: T = np.load(f"{sdir}/{night}.npz")["table"]
    except FileNotFoundError: continue
    for row in T:
        k = datetime.datetime.fromtimestamp(row[0] / 1000, datetime.UTC).strftime("%Y-%m-%dT%H")
        h = H.get(k)
        if not h or float(h["sun_alt"]) >= -18 or h["regime"].startswith(("E6", "E7")): continue
        if h["open_frac"] not in ("",) and float(h["open_frac"]) < 0.5: continue
        g = "moon up" if float(h["moon_alt"]) > 0 else "moonless"
        v = row[1] / float(h["regime_ref_stars"]); fr[g].append(v); hrs[g].setdefault(k, []).append(v)
def cls(v): v = np.array(v); return "clear" if v.min() >= HI else "cloudy" if v.max() < LO else "mixed"
fig, ax = plt.subplots(1, 2, figsize=(12, 4.8), facecolor="black")
bins = np.linspace(0, 1.6, 33)
for a, g in zip(ax, fr):
    a.set_facecolor("black"); v = np.clip(fr[g], 0, 1.59)
    n, _, p = a.hist(v, bins, color="#8E8E93", edgecolor="black")
    for pp, x in zip(p, bins[:-1]): pp.set_color("#FF3B30" if x < LO else "#30D158" if x >= HI else "#FF9500"); pp.set_edgecolor("black")
    c = [cls(x) for x in hrs[g].values() if len(x) >= 3]; N = len(c)
    txt = "\n".join(f"{k:7s}{c.count(k):4d} h  {100*c.count(k)/max(N,1):3.0f}%" for k in ("clear", "mixed", "cloudy"))
    a.text(0.97, 0.95, f"{g}: {N} dark hours\n{txt}", transform=a.transAxes, ha="right", va="top", color="#E0E0E0", family="monospace", fontsize=11)
    a.set_title(f"{g}: {len(v)} frames (one per 10 min)", color="#E0E0E0")
    a.set_xlabel("stars / regime's best-hours count", color="#8E8E93"); a.tick_params(colors="#8E8E93")
    for s in a.spines.values(): s.set_color("#2C2C2E")
ax[0].set_ylabel("frames", color="#8E8E93")
fig.suptitle(f"astrocam dark frames (sun < -18°), Jun-Nov 2026, water nights 10-25..11-11 left out.  red cloudy < {LO}, green clear >= {HI}, amber between.\n"
             f"Hour class: clear = every frame green, cloudy = every frame red, mixed = anything else", color="#E0E0E0", fontsize=10)
fig.tight_layout(); fig.savefig(png, dpi=110, facecolor="black")
for g in fr:
    h, _ = np.histogram(np.clip(fr[g], 0, 1.59), bins); print(g, len(fr[g]), "frames")
    for x, n in zip(bins, h): print(f"  {x:4.2f} {n:5d} " + "#" * int(60 * n / h.max()))
