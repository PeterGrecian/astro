"""Figure for the 'sharpest thing resolved' note: iota Ori + Struve 747, before/after deconvolution, two independent halves."""
import numpy as np, sys, json, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.argv = ["x"]; exec(open("/home/peter/astro/scratch/orion/deep/deconv.py").read().split("STARS = ")[0])
R = "/mnt/muppet/bigstore/eclipticam-frames/night"; D = "/home/peter/astro/scratch/orion/deep"
def half(nights):
    zs = [np.load(f"{R}/{n}/sword-stack-1s.npz", allow_pickle=True) for n in nights]
    Lb, h = prep({k: np.mean([q[k] for q in zs], 0) for k in "RGB"})
    s = 1.4826*np.median(np.abs(Lb[20:-20,20:-20]-np.median(Lb[20:-20,20:-20]))); return rl(Lb, s, 30)
deep = np.load(f"{D}/rl-deep-1s.npy")
P = [(deep[0], "9 nights, stacked"), (deep[1], "9 nights, deconvolved"),
     (half(["2026-09-17","2026-09-20","2026-09-21","2026-09-24"]), "September only, deconvolved"),
     (half(["2026-10-01","2026-10-02","2026-10-05","2026-10-07"]), "October only, deconvolved")]
pred = json.load(open("pred.json"))
pi = np.array([117.78, 141.47])                                   # iota Ori as measured (9 nights, deconvolved)
ps = pi + np.array(pred["STF 747 AB"]) - np.array(pred["iota Ori"])   # Struve 747 at the catalogue offset from it
x0, y0, b = int(round(pi[0])) + 1, int(round(pi[1])) + 1, 7
fig, ax = plt.subplots(1, 4, figsize=(16, 4.6), facecolor="black")
for a, (im, t) in zip(ax, P):
    c = np.clip(im[y0-b:y0+b+1, x0-b:x0+b+1], 0, None)
    a.imshow(np.sqrt(c / c.max()), cmap="turbo", interpolation="nearest", vmin=0, vmax=1, extent=[x0-b-.5, x0+b+.5, y0+b+.5, y0-b-.5])
    for p, lab in [(pi, "ι Ori"), (ps, "Struve 747")]:
        a.add_patch(plt.Circle(p, 1.3, fill=False, color="white", lw=1.2, ls="--"))
    a.annotate("ι Ori", pi + (-1.5, -2.0), color="white", fontsize=11, ha="right")
    a.annotate("Struve 747", ps + (1.6, 1.6), color="white", fontsize=11, ha="left", va="top")
    a.set_title(t, color="#E0E0E0", fontsize=12); a.set_axis_off()
plt.tight_layout(); plt.savefig("iota-stf747.png", dpi=100, facecolor="black")
