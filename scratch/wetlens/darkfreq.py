"""Darkness frequency through the archive: every astrocam frame's sky level above black, per second,
against the night it was taken. Marks the darkest 10% / 1% / 0.1% of the v3 era (from 2026-07-29,
one sensor) and how much exposure each night gives to the darkest 1% and 0.1%.
Level = frame MEAN above black (the csv median is integer ADU: 1/59.9 ADU/s steps tie the darkest frames).
Usage: darkfreq.py <out dir>"""
import csv, glob, os, sys, datetime, numpy as np, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
root = "/mnt/bigstore/astro-data/astrocam-frames"; out = sys.argv[1]; os.makedirs(out, exist_ok=True)
V3 = "2026-07-29"
rows = []                                                 # (night ordinal, rate, exptime, filename)
for bf in sorted(glob.glob(f"{root}/2026-*/brightness.csv")):
    night = os.path.basename(os.path.dirname(bf)); v3 = night >= V3
    ped = 64.0 if v3 else 512.0
    # exposure when the csv lacks it: v2 8x1.2 s co-adds; v3 59.9 s until 10-08, then 14.9 s
    ex0 = 14.9 if night >= "2026-10-09" else (59.9 if v3 else 9.6)
    for r in csv.DictReader(open(bf)):
        if r.get("cover", "") == "closed": continue
        try: med = float(r["mean"]); ex = float(r.get("exptime") or ex0)   # mean: the csv median is whole ADU and ties frames
        except (ValueError, KeyError, TypeError): continue
        if med - ped <= 0.5: continue                    # at black: glitch or covered
        rows.append((datetime.date.fromisoformat(night).toordinal(), (med - ped) / ex, ex, r.get("filename") or r.get("epoch_ms", ""), night))
d = np.array([r[0] for r in rows]); rate = np.array([r[1] for r in rows]); ex = np.array([r[2] for r in rows])
v3 = np.array([r[4] >= V3 for r in rows]); lr = np.log10(rate)
cut = {p: float(np.percentile(rate[v3], p)) for p in (0.1, 1, 10)}
summ = {f"darkest_{p}%": dict(threshold_adu_per_s=round(c, 4), frames=int((v3 & (rate <= c)).sum()),
        exposure_min=round(float(ex[v3 & (rate <= c)].sum() / 60), 1),
        nights=int(len(set(d[v3 & (rate <= c)])))) for p, c in cut.items()}
summ["v3_frames"] = int(v3.sum()); summ["v3_exposure_h"] = round(float(ex[v3].sum() / 3600), 1)
print(json.dumps(summ, indent=1))
# darkest frame lists, for accumulating
for p, c in cut.items():
    with open(f"{out}/darkest-{p}pct.csv", "w") as f:
        w = csv.writer(f); w.writerow(["night", "filename", "sky_adu_per_s", "exptime"])
        for r in sorted((r for r in rows if r[4] >= V3 and r[1] <= c), key=lambda r: r[1]): w.writerow([r[4], r[3], f"{r[1]:.4f}", r[2]])
json.dump(summ, open(f"{out}/darkness-summary.json", "w"), indent=1)

# ---- figure (house dark style)
BG, CARD, TXT, SEC, DIV = "#000000", "#161616", "#E0E0E0", "#8E8E93", "#2C2C2E"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "text.color": TXT, "axes.labelcolor": SEC,
                     "xtick.color": SEC, "ytick.color": SEC, "axes.edgecolor": DIV, "figure.facecolor": BG, "axes.facecolor": CARD})
seq = LinearSegmentedColormap.from_list("blue", ["#0B2545", "#1F5FA8", "#4C9BEF", "#A8D1FF", "#FFFFFF"])
fig = plt.figure(figsize=(18, 13)); gs = fig.add_gridspec(3, 2, width_ratios=[5, 1], height_ratios=[3, 1.3, 0.05], hspace=0.28, wspace=0.03)
ax = fig.add_subplot(gs[0, 0]); axh = fig.add_subplot(gs[0, 1], sharey=ax); axb = fig.add_subplot(gs[1, 0], sharex=ax)
n0, n1 = d.min(), d.max() + 1; yb = np.linspace(np.percentile(lr, 0.01) - 0.1, np.percentile(lr, 99.9), 120)
H, xe, ye = np.histogram2d(d, lr, bins=[np.arange(n0, n1 + 1) - 0.5, yb])
m = ax.pcolormesh(xe, ye, H.T, cmap=seq, norm=LogNorm(vmin=1, vmax=H.max()), shading="flat")
ax.axvspan(n0 - 0.5, datetime.date.fromisoformat(V3).toordinal() - 0.5, color="#FFFFFF", alpha=0.06, lw=0)
ax.text(n0 + 1, yb[-1] - 0.05, "v2 camera (imx219):\nother sensor and gain,\nnot in the percentiles", va="top", color=SEC, fontsize=11)
for p, ls in ((10, ":"), (1, "--"), (0.1, "-")):
    y = np.log10(cut[p]); ax.axhline(y, color=TXT, lw=1.2, ls=ls); axh.axhline(y, color=TXT, lw=1.2, ls=ls)
    axh.text(axh.get_xlim()[1] if False else 0.98, y, f" darkest {p}%", transform=axh.get_yaxis_transform(), ha="right", va="bottom", color=TXT, fontsize=11)
EVENTS = [("2026-08-20", "glass"), ("2026-10-09", "15 s subs"), ("2026-10-18", "repointed"), ("2026-10-25", "water ring"),
          ("2026-10-28", "storm"), ("2026-11-12", "washed")]
for t, lab in EVENTS:
    x = datetime.date.fromisoformat(t).toordinal() - 0.5
    for a in (ax, axb): a.axvline(x, color=SEC, lw=0.8, alpha=0.6)
    ax.text(x + 0.4, yb[0] + 0.05, lab, rotation=90, color=SEC, fontsize=10, va="bottom")
ax.set_ylabel("sky above black, log10 ADU per second")
ax.set_title("astrocam: how dark was every frame?  Each column is a night; brighter cell = more frames at that sky level",
             loc="left", color=TXT, fontsize=15, pad=12)
cb = fig.colorbar(m, cax=fig.add_subplot(gs[2, 0]), orientation="horizontal"); cb.set_label("frames per night per bin", color=SEC)
vv = lr[v3]; axh.hist(vv, bins=yb, orientation="horizontal", color="#4C9BEF", edgecolor=CARD, linewidth=0.5)
axh.set_xlabel("frames, v3 era"); plt.setp(axh.get_yticklabels(), visible=False)
nights = np.arange(n0, n1)
for p, col, lab in ((1, "#4C9BEF", "darkest 1%"), (0.1, "#A8D1FF", "darkest 0.1%")):
    sel = v3 & (rate <= cut[p]); mins = np.array([ex[sel & (d == n)].sum() / 60 for n in nights])
    axb.bar(nights, mins, width=0.8, color=col, label=f"{lab}: {summ[f'darkest_{p}%']['exposure_min']:.0f} min in {summ[f'darkest_{p}%']['nights']} nights")
axb.set_ylabel("minutes of exposure"); axb.legend(loc="upper left", frameon=False, labelcolor=TXT)
axb.set_title("where the darkest frames come from", loc="left", color=TXT, fontsize=13)
ticks = [datetime.date(2026, mo, 1).toordinal() for mo in range(6, 12)]
axb.set_xticks(ticks); axb.set_xticklabels([datetime.date.fromordinal(t).strftime("%-d %b") for t in ticks]); plt.setp(ax.get_xticklabels(), visible=False)
for a in (ax, axb, axh):
    for s in a.spines.values(): s.set_color(DIV)
fig.savefig(f"{out}/darkness-frequency.png", dpi=100, facecolor=BG); print("wrote", f"{out}/darkness-frequency.png")
