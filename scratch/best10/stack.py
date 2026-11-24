"""Multi-night stack of selected clear 10-min blocks onto one sky canvas (astro-science, Peter 2026-11-24).

Each night is stacked with `derot-sky stack --windows` (only frames inside its selected blocks; the
glow-fit cloud gate still applies) at a reference time with the SAME sidereal time as the base night's
reference, so every night's sky lands in the same orientation on one shared canvas. Per-night inputs
(glow model, camera model, align, ring residual) come from scratch/best10/inputs.sh. The per-night
stacks are then combined by summed frame weight (WEIGHT x WTMAX).

Usage: stack.py <out dir> <in dir> <base night> <ref HH:MM:SS> <regime> <selection.json> [+<canvas-only.json>] [...]
       stack.py --combine <out fits dir> <per-night stack dir> [...]"""
import sys, os, json, subprocess, importlib.machinery, importlib.util, datetime as dt
from pathlib import Path
import numpy as np
from astropy.io import fits
from scipy import ndimage as nd
HERE = Path.home() / "astro"; PY = str(HERE / ".venv/bin/python"); DS = str(HERE / "bin/derot-sky")
SID = 86164.0905
QMAX = float(os.environ.get("QMAX", 1.2))       # q above ~1.2 is spurious (lit cloud edges counted as stars, 10-06 20:08)
MAXR = os.environ.get("MAXR", "1e9")            # glow-fit gate off: per-night glow models fail on clear nights; blocks are star-selected
UTC = dt.timezone.utc

def load_ds():
    ld = importlib.machinery.SourceFileLoader("derot_sky", DS); sp = importlib.util.spec_from_loader("derot_sky", ld)
    m = importlib.util.module_from_spec(sp); ld.exec_module(m); return m

def ref_for(night, base, base_ref):           # same sidereal time as base_ref, on the given night
    k = (dt.date.fromisoformat(night) - dt.date.fromisoformat(base)).days
    return base_ref + dt.timedelta(seconds=k * SID)

def noise(m, w):                                # robust sky noise in the well-covered region
    v = m[(w > 0.3 * np.nanmax(w)) & np.isfinite(m)]
    return 1.4826 * np.median(np.abs(v - np.median(v))) if v.size > 1000 else np.inf

def lowpass(x, ok, k=8, size=9):              # masked median low-pass on a k-binned grid, back to full size
    H, W = x.shape; xb = np.where(ok, x, np.nan)[: H // k * k, : W // k * k].reshape(H // k, k, W // k, k)
    b = np.nanmedian(xb, (1, 3)); fill = np.isfinite(b)
    if not fill.any(): return np.zeros_like(x)
    idx = nd.distance_transform_edt(~fill, return_distances=False, return_indices=True)
    b = nd.median_filter(b[tuple(idx)], size)
    return np.pad(nd.zoom(b, k, order=1), ((0, H - H // k * k), (0, W - W // k * k)), mode="edge")[:H, :W]

def combine(out, dirs, iters=3):
    """Inverse-variance combine with per-night background matching. Nights register to <1 px, but each
    carries its own large-scale glow residual; the low-pass of (night - combined) over the night's coverage
    is removed (so the common Milky Way stays), then nights are weighted by coverage / noise^2."""
    St = []; frames = []
    for d in dirs:
        f = Path(d) / "derot-sky.fits"
        if not f.exists(): continue
        h = fits.getheader(f)
        if h.get("NFRAMES", 0) < 5: continue
        m, w = fits.getdata(f, 0).astype(np.float32), np.nan_to_num(fits.getdata(f, 1)).astype(np.float32)
        ok = (w > 0.3 * w.max()) & np.isfinite(m)
        St.append([Path(d).parent.parent.name + "/" + Path(d).name, h["NFRAMES"], np.nan_to_num(m), w, ok, None])
        frames += json.load(open(Path(d) / "derot-sky-frames.json")); h0 = h
    def comb():
        S = sum(np.where(s[4] | (s[3] > 0), s[2], 0) * s[3] / s[5] ** 2 for s in St); W = sum(s[3] / s[5] ** 2 for s in St)
        return np.where(W > 0, S / np.maximum(W, 1e-30), np.nan).astype(np.float32), W
    for s in St: s[5] = max(noise(s[2] - lowpass(s[2], s[4]), s[3]), 1e-3)     # first weights: high-passed noise
    if len(St) > 1:
      for it in range(iters):                     # match each night to the leave-one-out combination of the others
        S = sum(s[2] * s[3] / s[5] ** 2 for s in St); W = sum(s[3] / s[5] ** 2 for s in St)
        for s in St:
            Wo = W - s[3] / s[5] ** 2; loo = np.where(Wo > 1e-6 * W.max(), (S - s[2] * s[3] / s[5] ** 2) / np.maximum(Wo, 1e-30), np.nan)
            okc = s[4] & np.isfinite(loo)
            s[2] = s[2] - lowpass(s[2] - np.nan_to_num(loo), okc)
            d = s[2] - np.nan_to_num(loo); v = d[okc]
            s[5] = 1.4826 * np.median(np.abs(v - np.median(v))) if v.size > 1000 else 1e3   # includes the others' noise: a ranking, slightly flattened
    mean, W = comb()
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    h0["NFRAMES"] = sum(s[1] for s in St); h0["WTMAX"] = 1.0; h0["COMMENT"] = f"inverse-variance, background-matched combine of {len(St)} stacks"
    fits.HDUList([fits.PrimaryHDU(mean, h0), fits.ImageHDU((W / W.max()).astype(np.float32), name="WEIGHT")]).writeto(out / "derot-sky.fits", overwrite=True)
    json.dump(sorted(frames), open(out / "derot-sky-frames.json", "w"))
    tot = sum(1 / s[5] ** 2 for s in St)
    for s in sorted(St, key=lambda s: s[5])[:12]: print(f"    {s[0]:>22} {s[1]:4d} frames  resid-vs-others {s[5]:6.3f}  share {1 / s[5] ** 2 / tot:5.1%}")
    print(f"combined {len(St)} stacks, {h0['NFRAMES']} frames -> {out}")

def main():
    if sys.argv[1] == "--combine": return combine(sys.argv[2], sys.argv[3:])
    out, ind, base, ref, regime = sys.argv[1:6]; sels = sys.argv[6:]
    out, ind = Path(out), Path(ind); out.mkdir(parents=True, exist_ok=True)
    base_ref = dt.datetime.combine(dt.date.fromisoformat(base) + dt.timedelta(days=int(ref[:2]) < 12), dt.time.fromisoformat(ref), UTC)
    blocks, cblocks = {}, {}                 # a selection named "+file" shapes the canvas but is not stacked
    for s in sels:
        for b in json.load(open(s.lstrip("+"))):
            if b["regime"] == regime and b["q"] <= QMAX:
                cblocks.setdefault(b["night"], []).append(b["t_ms"])
                if not s.startswith("+"): blocks.setdefault(b["night"], []).append(b["t_ms"])
    ds = load_ds(); ds.EXPTIME_S = 59.9
    cam0 = ds.CameraModel(str(ind / base / "skyglow-cammodel.json"))
    # canvas: every selected block's frame border, rotated to the base reference, fits inside
    pseudo = []
    for night, ts in cblocks.items():
        sh = ref_for(night, base, base_ref) - base_ref
        for t in ts:
            t0 = dt.datetime.fromtimestamp(t / 1000, UTC) - sh
            pseudo += [(t0 + dt.timedelta(minutes=m), None) for m in (0, 5, 10)]
    pseudo.sort(key=lambda f: f[0])
    q, shape = ds.canvas_geometry(cam0, [f for f in pseudo for _ in range(10)], base_ref, (1296, 2304))   # every pseudo frame (it samples [::10]); 2x2-binned frame shape
    cfile = out / "canvas-model.json"; json.dump(dict(q, shape=list(shape)), open(cfile, "w"), indent=1)
    print(f"canvas {shape[1]} x {shape[0]}, {len(blocks)} nights, {sum(map(len, blocks.values()))} blocks, base ref {base_ref:%Y-%m-%d %H:%M:%S}")
    done = []
    for night in sorted(blocks):
        D = ind / night; o = out / "nights" / night
        need = [D / f for f in ("skyglow-model.npz", "skyglow-cammodel.json")]
        if not all(p.exists() for p in need): print(f"  {night}: inputs missing, skipped"); continue
        o.mkdir(parents=True, exist_ok=True)
        win = [[dt.datetime.fromtimestamp(t / 1000, UTC).isoformat(), dt.datetime.fromtimestamp(t / 1000 + 600, UTC).isoformat()] for t in sorted(blocks[night])]
        json.dump(win, open(o / "windows.json", "w"))
        r = ref_for(night, base, base_ref)
        cmd = [PY, DS, "stack", str(D / "skyglow-cammodel.json"), night, "--glow", str(D / "skyglow-model.npz"),
               "--ref-utc", r.strftime("%H:%M:%S"), "--windows", str(o / "windows.json"), "--canvas-from", str(cfile), "--max-ratio", MAXR, "-j", "2", "-o", str(o)]
        if (D / "align.npy").exists(): cmd += ["--align", str(D / "align.npy")]
        rs = sorted(ind.glob("*/resid.npy"), key=lambda p: abs((dt.date.fromisoformat(p.parent.name) - dt.date.fromisoformat(night)).days))
        if rs: cmd += ["--residual", str(rs[0])]           # own ring map, else the nearest night's (camera-fixed)
        res = subprocess.run(["nice", "-n", "15"] + cmd, capture_output=True, text=True, env=dict(os.environ, DEROT_CAMERA="astrocam"))
        last = [l for l in res.stdout.splitlines() if "stacked" in l or "noise" in l]
        print(f"  {night}: {len(win)} blocks, ref {r:%H:%M:%S}: {' | '.join(last) or res.stderr.strip().splitlines()[-1:]}", flush=True)
        if res.returncode == 0: done.append(str(o))
    combine(out / "all", done)

if __name__ == "__main__": main()
