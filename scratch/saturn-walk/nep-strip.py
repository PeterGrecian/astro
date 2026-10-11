"""Neptune's five nights side by side on the same patch of sky, plus the swap test:
the signal at each night's Neptune position measured in every other night's stack."""
import importlib.util, json, math
import numpy as np
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
spec = importlib.util.spec_from_file_location("nf", "nep-find.py"); nf = importlib.util.module_from_spec(spec); spec.loader.exec_module(nf)
N = ["2026-09-20", "2026-09-24", "2026-10-01", "2026-10-05", "2026-10-07"]
res = {n: nf.main(n) for n in N}
F = {}
for n in N:
    z = np.load(f"nep/{n}.npz"); S = z["stack"] - ndi.median_filter(z["stack"], 41)
    F[n] = ndi.gaussian_filter(S, 1.2) / (1.4826 * np.median(np.abs(S - np.median(S))))
print("\nsmoothed sigma at each night's Neptune position (rows: stack, cols: position night)")
print("            " + "  ".join(n[5:] for n in N))
for a in N:
    print(a[5:], "     ", "  ".join(f"{F[a][int(round(res[b]['pred'][1])), int(round(res[b]['pred'][0]))]:5.1f}" for b in N))
x0, x1, y0, y1 = 70, 125, 50, 92
fig, ax = plt.subplots(len(N), 1, figsize=(9, 2.0 * len(N)))
for a, n in zip(ax, N):
    a.imshow(F[n][y0:y1, x0:x1], cmap="gray", vmin=-1, vmax=8)
    for m in N:
        px, py = res[m]["pred"]
        a.plot(px - x0, py - y0, "o", mfc="none", mec="#00a0ff" if m == n else "#555", ms=14, mew=1.5)
    a.set_ylabel(n[5:], rotation=0, labelpad=22); a.set_xticks([]); a.set_yticks([])
ax[0].set_title("Neptune, eclipticam: each night ~200-250 x 60 s stacked on the stars\nblue = that night's ephemeris, grey = the other nights'")
fig.tight_layout(); fig.savefig("nep/strip.png", dpi=90)
