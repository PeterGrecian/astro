"""Per-frame star count and across-trail width on a 3x3 grid, sampled through recent nights.
Water on the lens shows as cells losing stars or widening while others stay sharp."""
import os, sys, glob, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
root = os.environ["BIGSTORE"] + "/astrocam-frames"
nights = sys.argv[1:] or ["2026-10-25", "2026-10-26", "2026-10-27"]
def load(p):
    with fits.open(p) as h:
        for x in h:
            if x.data is not None:
                d, hdr = x.data.astype(np.float32), x.header; break
    if d.ndim == 3: d = d.mean(axis=0) if d.shape[0] <= 4 else d.mean(axis=2)
    return d, hdr
first = True
for n in nights:
    fs = sorted(glob.glob(f"{root}/{n}/[0-2][0-9]/*.fits.fz"))
    for p in fs[::120]:
        d, hdr = load(p)
        if first: print("shape", d.shape, "keys", [k for k in ("COVER","EXPTIME","BOXRH","LENSPOS") if k in hdr]); first = False
        bg = nd.median_filter(d[::4, ::4], 15); bg = nd.zoom(bg, 4, order=1)[:d.shape[0], :d.shape[1]]
        r = d - bg; s = 1.4826 * np.median(np.abs(r - np.median(r)))
        pk = (r == nd.maximum_filter(r, 7)) & (r > 8 * s)
        ys, xs = np.nonzero(pk); H, W = d.shape
        cnt = np.zeros((3, 3), int); wid = [[[] for _ in range(3)] for _ in range(3)]
        for y, x in zip(ys, xs):
            if y < 5 or x < 5 or y > H - 6 or x > W - 6: continue
            st = np.clip(r[y-5:y+6, x-5:x+6], 0, None); f = st.sum()
            if f <= 0: continue
            yy, xx = np.mgrid[-5:6, -5:6]; my, mx = (st*yy).sum()/f, (st*xx).sum()/f
            c = np.cov(np.vstack([(xx-mx).ravel(), (yy-my).ravel()]), aweights=st.ravel())
            gi, gj = min(2, 3*y//H), min(2, 3*x//W); cnt[gi, gj] += 1
            wid[gi][gj].append(np.sqrt(max(np.linalg.eigvalsh(c)[0], 0)))
        w = np.array([[np.median(c) if c else np.nan for c in row] for row in wid])
        t = os.path.basename(p).split(".")[0]
        import datetime; ts = datetime.datetime.utcfromtimestamp(int(t)/1000).strftime("%m-%d %H:%M")
        print(ts, hdr.get("COVER","-"), "n", cnt.sum(), "| cnt", " ".join("".join(f"{v:4d}" for v in row) for row in cnt),
              "| wid", " ".join("".join(f"{v:5.2f}" for v in row) for row in w))
