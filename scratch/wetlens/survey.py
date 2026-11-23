"""Water-damage survey of astrocam, every night: which frames/nights carry water marks.

Per night, one frame every ~10 min in the dark hours (17-06 UTC):
  - star count and star size (2nd-moment radius, binned px) in each 3x3 cell: water on the lens
    blurs or kills stars in some cells while others stay sharp;
  - a clear-sky flat: median of the clear frames, each normalised by its own median, binned 8
    (576x324), stars filtered out. Spots, rings, drips show in the ratio of one night's flat to a
    clean reference night's.
Writes <out>/<night>.npz (flat, per-frame table) and prints one line per night.
Usage: survey.py <out dir> <night> [<night> ...]"""
import os, sys, glob, datetime, numpy as np
from astropy.io import fits
from scipy import ndimage as nd
root = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/astrocam-frames"
out = sys.argv[1]; os.makedirs(out, exist_ok=True)

def load(p):
    with fits.open(p) as h:
        for x in h:
            if x.data is not None:
                d, hdr = x.data.astype(np.float32), x.header; break
    if d.ndim == 3: d = d.mean(axis=0) if d.shape[0] <= 4 else d.mean(axis=2)
    return d, hdr

def stars(d):
    b = d[: d.shape[0] // 2 * 2, : d.shape[1] // 2 * 2].reshape(d.shape[0] // 2, 2, d.shape[1] // 2, 2).mean((1, 3))
    bg = nd.zoom(nd.median_filter(b[::8, ::8], 9), 8, order=1)[: b.shape[0], : b.shape[1]]
    r = b - bg; s = 1.4826 * np.median(np.abs(r[::4, ::4] - np.median(r[::4, ::4])))
    pk = (r == nd.maximum_filter(r, 5)) & (r > 8 * s)
    ys, xs = np.nonzero(pk); H, W = b.shape
    cnt = np.zeros((3, 3)); sz = [[[] for _ in range(3)] for _ in range(3)]
    yy, xx = np.mgrid[-3:4, -3:4]
    for y, x in zip(ys, xs):
        if y < 4 or x < 4 or y > H - 5 or x > W - 5: continue
        st = np.clip(r[y - 3:y + 4, x - 3:x + 4], 0, None); f = st.sum()
        if f <= 0: continue
        my, mx = (st * yy).sum() / f, (st * xx).sum() / f
        rad = np.sqrt((st * ((yy - my) ** 2 + (xx - mx) ** 2)).sum() / f)
        i, j = min(2, 3 * y // H), min(2, 3 * x // W); cnt[i, j] += 1; sz[i][j].append(rad)
    size = np.array([[np.median(c) if len(c) >= 5 else np.nan for c in row] for row in sz])
    return cnt, size, s

for night in sys.argv[2:]:
    fs = sorted(glob.glob(f"{root}/{night}/[0-2][0-9]/*.fits.fz"), key=os.path.basename)
    fs = [p for p in fs if os.path.basename(os.path.dirname(p)) in {f"{h:02d}" for h in list(range(17, 24)) + list(range(0, 6))}]
    if not fs: print(night, "no dark frames"); continue
    def tms(p):                                     # ms-epoch names (from 2026-09), else summer's HH/SSSS (seconds into the hour)
        b = os.path.basename(p).split(".")[0]
        if len(b) > 6: return int(b)
        hh = int(os.path.basename(os.path.dirname(p))); day = datetime.date.fromisoformat(night) + datetime.timedelta(days=hh < 12)
        return int((datetime.datetime(day.year, day.month, day.day, hh, tzinfo=datetime.UTC).timestamp() + int(b)) * 1000)
    fs = sorted(fs, key=tms); ts = np.array([tms(p) for p in fs]); pick, last = [], -1e18
    for k, t in enumerate(ts):
        if t - last >= 600_000: pick.append(k); last = t
    rows, flats = [], []
    for k in pick:
        try: d, hdr = load(fs[k])
        except Exception as e: print("  skip", fs[k], e); continue
        cnt, size, s = stars(d)
        b8 = d[: d.shape[0] // 8 * 8, : d.shape[1] // 8 * 8].reshape(d.shape[0] // 8, 8, d.shape[1] // 8, 8).mean((1, 3))
        b8 = nd.median_filter(b8, 3); m = np.median(b8)
        flats.append((b8 / m).astype(np.float32))
        rows.append((ts[k], cnt.sum(), *cnt.ravel(), *size.ravel(), m, s, float(hdr.get("BOXRH", np.nan) or np.nan),
                     1.0 if str(hdr.get("COVER", "")).lower().startswith("open") else 0.0))
    T = np.array(rows, float); F = np.array(flats)
    n = T[:, 1]; clear = n >= max(30, 0.5 * np.percentile(n, 90))
    flat = np.median(F[clear], 0) if clear.sum() >= 3 else np.full(F.shape[1:], np.nan, np.float32)
    np.savez_compressed(f"{out}/{night}.npz", table=T, flat=flat, clear=clear, files=np.array([fs[k] for k in pick]))
    sz = T[clear][:, 11:20] if clear.any() else np.full((1, 9), np.nan)
    msz = np.nanmedian(sz, 0); spread = np.nanmax(msz) / np.nanmin(msz) if np.isfinite(msz).sum() >= 5 else np.nan
    print(f"{night} sampled {len(T):3d} clear {clear.sum():3d} stars(p90) {np.percentile(n, 90):5.0f} "
          f"size med {np.nanmedian(msz):.2f} worst/best cell {spread:.2f} rh {np.nanmedian(T[:, 22]):.0f}", flush=True)
