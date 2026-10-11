"""Colour-colour figure for the Orion note: red and blue with green scaled to 1, relative to white."""
import json, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
rows = json.load(open("colour-rows.json"))
STARS = ["Rigel","Bellatrix","Saiph","Alnitak","Alnilam","Mintaka","mu Ori","pi2 Ori","pi3 Ori","Betelgeuse"]
lbl = {"mu Ori":"μ Ori","pi2 Ori":"π² Ori","pi3 Ori":"π³ Ori"}
pos = {"Bellatrix":(0.74,1.16),"Mintaka":(0.74,1.10),"Alnilam":(0.80,1.04),"Alnitak":(0.90,1.18),"Saiph":(1.00,1.15),
       "Rigel":(1.08,1.09),"mu Ori":(1.11,1.00),"pi2 Ori":(0.86,0.95)}
v = {s: (np.median([q["R"]/q["G"] for q in rows if q["star"] == s]), np.median([q["B"]/q["G"] for q in rows if q["star"] == s])) for s in STARS}
wr = np.mean([v[s][0] for s in ("mu Ori","pi2 Ori")]); wb = np.mean([v[s][1] for s in ("mu Ori","pi2 Ori")])
fig, ax = plt.subplots(figsize=(8, 6), facecolor="black"); ax.set_facecolor("#161616")
for s, (rg, bg) in v.items():
    x, y = rg / wr, bg / wb; c = np.array([x, 1, y]); c = c / c.max()
    ax.scatter(x, y, s=260 if s in ("Betelgeuse", "Rigel") else 120, color=c, edgecolor="#8E8E93", zorder=3)
    ax.annotate(lbl.get(s, s), (x, y), xytext=pos.get(s, (x + 0.04, y)), color="#E0E0E0", fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color="#8E8E93", lw=0.6) if s in pos else None)
ax.axvline(1, color="#2C2C2E"); ax.axhline(1, color="#2C2C2E")
ax.set_xlabel("red (green = 1), relative to white (μ and π² Ori)", color="#E0E0E0")
ax.set_ylabel("blue (green = 1), relative to white", color="#E0E0E0")
ax.tick_params(colors="#8E8E93"); [sp.set_color("#2C2C2E") for sp in ax.spines.values()]
ax.set_xlim(0.7, 1.95); ax.set_ylim(0.38, 1.22)
ax.text(1.55, 1.17, "↑ bluer   redder →", color="#8E8E93")
plt.tight_layout(); plt.savefig("orion-colours.png", dpi=110, facecolor="black")
