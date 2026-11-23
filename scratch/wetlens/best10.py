"""Rank every dark 10-min block (survey sample) by star count / regime ref; list the best 10% and next 10%,
grouped by night, with which per-night inputs exist for derot-sky stack. Usage: best10.py <survey dir> <out dir>"""
import sys, os, csv, json, datetime, numpy as np
sdir, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
B = "/mnt/bigstore/astro-data/astrocam-frames"
H = {r["hour"]: r for r in csv.DictReader(open(f"{sdir}/hours.csv"))}
S = []
for night in sorted({r["night"] for r in H.values()}):
    try: T = np.load(f"{sdir}/{night}.npz")["table"]
    except FileNotFoundError: continue
    for row in T:
        k = datetime.datetime.fromtimestamp(row[0] / 1000, datetime.UTC).strftime("%Y-%m-%dT%H"); h = H.get(k)
        if not h or float(h["sun_alt"]) >= -18 or h["regime"].startswith(("E6", "E7")): continue
        S.append((row[1] / float(h["regime_ref_stars"]), int(row[0]), night, h["regime"], float(h["moon_alt"]) > 0))
S.sort(key=lambda s: -s[0]); n = len(S); d = n // 10
for name, sel in (("best10", S[:d]), ("next10", S[d:2 * d])):
    json.dump([dict(q=round(q, 3), t_ms=t, night=nt, regime=r, moon=m) for q, t, nt, r, m in sel], open(f"{out}/{name}.json", "w"))
    print(f"{name}: {len(sel)} blocks of 10 min = {len(sel)/6:.0f} h, q {sel[-1][0]:.2f}..{sel[0][0]:.2f}, moon up {sum(s[4] for s in sel)}")
    by = {}
    for s in sel: by.setdefault((s[2], s[3]), []).append(s)
    for (nt, r), v in sorted(by.items()):
        have = "".join(c for c, f in (("g", "skyglow-model.npz"), ("c", "skyglow-cammodel.json"), ("a", "derot-sky-align.npy")) if os.path.exists(f"{B}/{nt}/{f}"))
        print(f"   {nt} {r:15s} {len(v):3d} {have}")
