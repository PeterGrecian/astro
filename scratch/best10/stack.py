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
HERE = Path.home() / "astro"; PY = str(HERE / ".venv/bin/python"); DS = str(HERE / "bin/derot-sky")
SID = 86164.0905
UTC = dt.timezone.utc

def load_ds():
    ld = importlib.machinery.SourceFileLoader("derot_sky", DS); sp = importlib.util.spec_from_loader("derot_sky", ld)
    m = importlib.util.module_from_spec(sp); ld.exec_module(m); return m

def ref_for(night, base, base_ref):           # same sidereal time as base_ref, on the given night
    k = (dt.date.fromisoformat(night) - dt.date.fromisoformat(base)).days
    return base_ref + dt.timedelta(seconds=k * SID)

def combine(out, dirs):
    S = W = None; n = 0; frames = []
    for d in dirs:
        f = Path(d) / "derot-sky.fits"
        if not f.exists(): continue
        m, w = fits.getdata(f, 0), fits.getdata(f, 1); h = fits.getheader(f); w = w * h["WTMAX"]
        S = np.nan_to_num(m) * w if S is None else S + np.nan_to_num(m) * w
        W = w.copy() if W is None else W + w; n += h["NFRAMES"]
        frames += json.load(open(Path(d) / "derot-sky-frames.json")); h0 = h
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    mean = np.where(W > 0, S / np.maximum(W, 1e-30), np.nan).astype(np.float32)
    h0["NFRAMES"] = n; h0["WTMAX"] = float(W.max()); h0["COMMENT"] = f"combined from {len(dirs)} stacks by summed frame weight"
    fits.HDUList([fits.PrimaryHDU(mean, h0), fits.ImageHDU((W / W.max()).astype(np.float32), name="WEIGHT")]).writeto(out / "derot-sky.fits", overwrite=True)
    json.dump(sorted(frames), open(out / "derot-sky-frames.json", "w"))
    good = W > 0.3 * W.max(); v = mean[good]; sig = 1.4826 * np.median(np.abs(v - np.median(v)))
    print(f"combined {len(dirs)} stacks, {n} frames -> {out}  noise sigma {sig:.3f} ADU (well-covered)")

def main():
    if sys.argv[1] == "--combine": return combine(sys.argv[2], sys.argv[3:])
    out, ind, base, ref, regime = sys.argv[1:6]; sels = sys.argv[6:]
    out, ind = Path(out), Path(ind); out.mkdir(parents=True, exist_ok=True)
    base_ref = dt.datetime.combine(dt.date.fromisoformat(base) + dt.timedelta(days=int(ref[:2]) < 12), dt.time.fromisoformat(ref), UTC)
    blocks, cblocks = {}, {}                 # a selection named "+file" shapes the canvas but is not stacked
    for s in sels:
        for b in json.load(open(s.lstrip("+"))):
            if b["regime"] == regime:
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
               "--ref-utc", r.strftime("%H:%M:%S"), "--windows", str(o / "windows.json"), "--canvas-from", str(cfile), "-j", "2", "-o", str(o)]
        if (D / "align.npy").exists(): cmd += ["--align", str(D / "align.npy")]
        if (D / "resid.npy").exists(): cmd += ["--residual", str(D / "resid.npy")]
        res = subprocess.run(["nice", "-n", "15"] + cmd, capture_output=True, text=True, env=dict(os.environ, DEROT_CAMERA="astrocam"))
        last = [l for l in res.stdout.splitlines() if "stacked" in l or "noise" in l]
        print(f"  {night}: {len(win)} blocks, ref {r:%H:%M:%S}: {' | '.join(last) or res.stderr.strip().splitlines()[-1:]}", flush=True)
        if res.returncode == 0: done.append(str(o))
    combine(out / "all", done)

if __name__ == "__main__": main()
