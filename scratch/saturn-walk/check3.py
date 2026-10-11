#!/usr/bin/env python3
"""Saturn three-night check on eclipticam (astro-science, 2026-10-10).

Is Saturn where the ephemeris says, on three nights spanning the retrograde
run, when each night's pointing is fitted from catalogue stars ONLY?

Not circular by construction: Saturn is not in the catalogue, and every
catalogue star within EXCL px of Saturn's predicted pixel is dropped before
the fit, so nothing in the pointing solution can see the planet. The local
star residuals near Saturn are the control: if Saturn's residual is no bigger
than theirs, the method holds.

Per frame: 2x2-binned luminance, block-median background removed, pointing
(az0, alt0, roll) refined against Hipparcos V<7.5 (f, k, centre fixed from the
10-07 solve), then Saturn centroided and converted back to RA/Dec.
Times are mid-exposure for stars and planet alike (both trail ~4 px in 60 s).

Run on muppet:  bigstore-run scratch/saturn-walk/check3.py
"""
import glob, json, os, sys, warnings
from datetime import datetime, timedelta, timezone

import numpy as np
from astropy.io import fits
from scipy.ndimage import maximum_filter, zoom
from scipy.optimize import least_squares

warnings.filterwarnings("ignore")
ASTRO = os.path.expanduser("~/astro")
sys.path.insert(0, ASTRO)
from astro.skyglow import CameraModel, _enu  # noqa: E402
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body  # noqa: E402
from astropy.time import Time  # noqa: E402
import astropy.units as u  # noqa: E402

BASE = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/eclipticam-frames/night"
CAM = f"{ASTRO}/eclipticam-v3w/cammodel-2026-10-07.json"
OUT = f"{ASTRO}/scratch/saturn-walk"
EXCL = 25          # px: catalogue stars this close to Saturn are not used
LOCAL = 350        # px: final pointing fit uses only stars this close to Saturn
NIGHTS = [         # (night, UTC window start, end) with Saturn well inside the frame
    ("2026-08-12", "02:30", "03:00"),   # 07-27: Saturn at the far edge, glare; model fails there
    ("2026-09-05", "01:00", "01:30"),
    ("2026-10-07", "23:15", "23:45"),
]
NPER = 6
os.makedirs(OUT, exist_ok=True)
P = json.load(open(CAM))
LOC = EarthLocation(lat=P["lat"] * u.deg, lon=P["lon"] * u.deg)
STARS = np.array(P["stars_radec_j2000"])
_H = f"{OUT}/hip75.npy"   # same 6844 stars with V (from muppet ~/tmp/eclsolve)
VMAG = np.load(_H)[:, 2] if os.path.exists(_H) else None
if os.environ.get("STARS_ALLSKY"):   # the model's 6844 stars stop at RA ~60 deg (no Taurus); Hipparcos V<7.5, dec > -35, from VizieR I/239
    _A = np.load(f"{OUT}/hip75-allsky.npy")
    STARS, VMAG = _A[:, :2], _A[:, 2]


def utc(night, hm):
    d = datetime.strptime(night, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    h, m = map(int, hm.split(":"))
    return d + timedelta(days=0 if h >= 12 else 1, hours=h, minutes=m)


def frames(night, t0, t1):
    out = []
    for p in glob.glob(f"{BASE}/{night}/v3w/[0-2][0-9]/*.fits.fz"):
        t = datetime.fromtimestamp(int(os.path.basename(p).split(".")[0]) / 1000, timezone.utc)
        if t0 <= t <= t1:
            out.append((t, p))
    out.sort()
    idx = np.linspace(0, len(out) - 1, min(NPER, len(out))).round().astype(int)
    return [out[i] for i in sorted(set(idx))]


def load(path):
    with fits.open(path) as h:
        d = h[1].data.astype(np.float32)
        exp = float(h[1].header.get("EXPTIME", 59.9))
    H, W = d.shape
    b = d[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2).sum(axis=(1, 3))
    # block-median background (32 px blocks), smooth upsample
    B = 32
    h2, w2 = b.shape[0] // B, b.shape[1] // B
    med = np.median(b[:h2 * B, :w2 * B].reshape(h2, B, w2, B).transpose(0, 2, 1, 3).reshape(h2, w2, -1), axis=2)
    bg = zoom(med, (b.shape[0] / h2, b.shape[1] / w2), order=1)
    return b - bg, exp


def enu_of(sc, t):
    aa = sc.transform_to(AltAz(obstime=Time(t), location=LOC, pressure=0))
    return _enu(np.radians(np.atleast_1d(aa.az.deg)), np.radians(np.atleast_1d(aa.alt.deg)))


def centroid(img, x, y, r, noise, need=8, thr=5):
    """Flux-weighted centroid of the connected blob (pixels > thr sigma) that
    holds the brightest pixel within r of (x, y). Whole trails, not a fixed
    box: near the frame edge a 60 s trail is ~10 px long, and a 7x7 box cuts
    it off and pulls the centroid toward the peak end."""
    from scipy.ndimage import label
    H, W = img.shape
    xi, yi = int(round(x)), int(round(y))
    R = r + 14
    if not (R <= xi < W - R and R <= yi < H - R):
        return None
    big = img[yi - R:yi + R + 1, xi - R:xi + R + 1]
    cut = big[R - r:R + r + 1, R - r:R + r + 1]
    j = np.unravel_index(np.argmax(cut), cut.shape)
    if cut[j] < need * noise:
        return None
    lab, _ = label(big > thr * noise)
    k = lab[R - r + j[0], R - r + j[1]]
    m = lab == k
    if m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any():
        return None          # blob runs off the box: blended or not a star
    gy, gx = np.nonzero(m)
    w = big[gy, gx]
    return (xi - R + (w * gx).sum() / w.sum(), yi - R + (w * gy).sum() / w.sum(), float(cut[j] / noise))

def model(p):
    tmp = f"{OUT}/.cm-{os.getpid()}.json"
    json.dump({k: v for k, v in p.items() if k != "stars_radec_j2000"}, open(tmp, "w"))   # the star list is 6844 pairs
    m = CameraModel(tmp)
    os.remove(tmp)
    return m


def _proj(V, az0, alt0, roll, f, k, cx, cy, mirror):
    """CameraModel.project inlined for the pointing grid (no JSON round trip)."""
    b = _enu(np.array(az0), np.array(alt0))
    e1 = np.cross([0, 0, 1.0], b); e1 /= np.linalg.norm(e1)
    e2 = np.cross(b, e1)
    ex, ey = np.cos(roll) * e1 + np.sin(roll) * e2, -np.sin(roll) * e1 + np.cos(roll) * e2
    th = np.arccos(np.clip(V @ b, -1, 1))
    r = f * (th + k * th ** 3)
    phi = np.arctan2(V @ ey, V @ ex)
    return cx + mirror * r * np.cos(phi), cy - r * np.sin(phi), th


def detections(img, noise, n=400):
    from scipy.ndimage import maximum_filter as mf
    pk = (img == mf(img, size=7)) & (img > 10 * noise)
    pk[:40] = pk[-40:] = False; pk[:, :40] = pk[:, -40:] = False
    ys, xs = np.nonzero(pk)
    o = np.argsort(img[ys, xs])[::-1][:n]
    return np.c_[xs[o], ys[o]].astype(float)


def grid_pointing(img, noise, V, p):
    """Coarse blind search over (az0, alt0, roll) about the 10-07 pointing.
    The camera has moved by degrees between epochs (rose-bush era <= 08-22),
    which a pixel shift cannot absorb. Bright stars only (V < 5) against the
    brightest 150 detections, and the score is matches MINUS the chance
    matches expected for that many predictions: a raw count rewards pointings
    that merely put more catalogue stars in the frame."""
    from scipy.spatial import cKDTree
    det = detections(img, noise, n=150)
    tree = cKDTree(det)
    H, W = img.shape
    keep = (V[:, 2] > np.sin(np.radians(10))) & (VMAG < 5.0)
    V = V[keep]
    best = (-1e9, p["az0"], p["alt0"], p["roll"], 0)
    for step, span, tol in ((np.radians(0.8), np.radians([30, 15, 12]), 14),
                            (np.radians(0.15), np.radians([1.0, 1.0, 1.0]), 4)):
        a0, l0, r0 = best[1:4]
        best = (-1e9, a0, l0, r0, 0)
        for az in a0 + np.arange(-span[0], span[0] + 1e-9, step):
            for al in l0 + np.arange(-span[1], span[1] + 1e-9, step):
                for ro in r0 + np.arange(-span[2], span[2] + 1e-9, step):
                    x, y, th = _proj(V, az, al, ro, p["f"], p["k"], p["cx"], p["cy"], p["mirror"])
                    m = (th < np.radians(75)) & (x > 40) & (x < W - 40) & (y > 40) & (y < H - 40)
                    n = int(m.sum())
                    if n < 15:
                        continue
                    d, _ = tree.query(np.c_[x[m], y[m]], distance_upper_bound=tol)
                    hits = int(np.isfinite(d).sum())
                    sc = hits - n * len(det) * np.pi * tol ** 2 / (W * H)
                    if sc > best[0]:
                        best = (sc, az, al, ro, hits)
    print(f"  grid: {best[4]} bright-star hits (excess {best[0]:.0f}); pointing moved "
          f"az {np.degrees(best[1] - p['az0']):+.2f} alt {np.degrees(best[2] - p['alt0']):+.2f} "
          f"roll {np.degrees(best[3] - p['roll']):+.2f} deg from 10-07", flush=True)
    return dict(p, az0=float(best[1]), alt0=float(best[2]), roll=float(best[3]))

def bootstrap(img, t, p, night):
    """Blind per-night pointing: astrometry.net on sky crops of one frame, then
    fit (az0, alt0, roll, f) of the camera model to the pooled crop matches.
    The three nights are three different set-ups (rose-bush garden, window
    with curtain, window turned), so nothing carries over from 10-07 but the
    lens (k, centre, mirror)."""
    import subprocess, tempfile
    wd = tempfile.mkdtemp(prefix=f"boot-{night}-", dir=OUT)
    H, W = img.shape
    pairs = []
    for x0 in (100, 650, 1200, 1750):
        for y0 in (40, 380):
            cut = np.nan_to_num(img[y0:y0 + 420, x0:x0 + 500]).clip(-50, None).astype(np.float32)
            fn = f"{wd}/c{x0}_{y0}.fits"
            fits.PrimaryHDU(cut).writeto(fn, overwrite=True)
            subprocess.run(["solve-field", fn, "--overwrite", "--no-plots", "--no-remove-lines",
                            "--scale-units", "arcsecperpix", "--scale-low", "150", "--scale-high", "320",
                            "--cpulimit", "40", "--objs", "80", "--crpix-center", "--no-verify"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            corr = fn.replace(".fits", ".corr")
            if not os.path.exists(corr):
                continue
            with fits.open(corr) as h:
                c = h[1].data
                n0 = len(pairs)
                for r in c:
                    pairs.append((r["field_x"] - 1 + x0, r["field_y"] - 1 + y0, r["index_ra"], r["index_dec"]))
            print(f"    crop ({x0},{y0}) solved, {len(pairs) - n0} matches", flush=True)
    pairs = np.array(pairs)
    if len(pairs) < 8:
        raise SystemExit(f"{night}: bootstrap found only {len(pairs)} matches")
    V = enu_of(SkyCoord(pairs[:, 2] * u.deg, pairs[:, 3] * u.deg), t)

    def resid(q):
        x, y, _ = _proj(V, q[0], q[1], q[2], q[3], p["k"], p["cx"], p["cy"], p["mirror"])
        return np.concatenate([x - pairs[:, 0], y - pairs[:, 1]])

    # start from the sky direction of the matches' centroid, a few rolls
    vbar = V.mean(0); vbar /= np.linalg.norm(vbar)
    az_c, alt_c = np.arctan2(vbar[0], vbar[1]), np.arcsin(vbar[2])
    best = None
    for daz in np.radians(np.arange(-20, 21, 10)):
        for dal in np.radians(np.arange(-15, 16, 7.5)):
            for ro in np.radians(np.arange(-40, 41, 10)):
                s = least_squares(resid, [az_c + daz, alt_c + dal, ro, p["f"]], loss="soft_l1", f_scale=2.0)
                if best is None or s.cost < best.cost:
                    best = s
    d = np.hypot(*np.split(best.fun, 2))
    print(f"  bootstrap: {len(pairs)} matches, median {np.median(d):.2f} px; az0 {np.degrees(best.x[0]) % 360:.2f} "
          f"alt0 {np.degrees(best.x[1]):.2f} roll {np.degrees(best.x[2]):.2f} f {best.x[3]:.1f}", flush=True)
    return dict(p, az0=float(best.x[0]), alt0=float(best.x[1]), roll=float(best.x[2]), f=float(best.x[3]))


def fit_frame(t_start, path, p0=None, body="saturn"):
    """Pointing fit local to `body` (masked from the fit), then the body's centroid.
    Record keys say sat_* whatever the body is."""
    img, exp = load(path)
    t = t_start + timedelta(seconds=exp / 2)
    noise = 1.4826 * np.median(np.abs(img - np.median(img)))
    H, W = img.shape
    sat_sc = get_body(body, Time(t), LOC)
    Vs = enu_of(sat_sc, t)
    V = enu_of(SkyCoord(STARS[:, 0] * u.deg, STARS[:, 1] * u.deg), t)
    p = dict(p0 or P)
    cm = model(p)
    sx0, sy0 = (float(a[0]) for a in cm.project(Vs))
    px, py = cm.project(V)
    alt_ok = V[:, 2] > np.sin(np.radians(12))
    far = np.hypot(px - sx0, py - sy0) > EXCL
    inb = (px > 60) & (px < W - 60) & (py > 60) & (py < H - 60) & alt_ok & far
    # coarse whole-pattern shift (camera nudges between nights)
    sm = maximum_filter(np.clip(img / noise, 0, 50), size=3)
    xi0, yi0 = np.round(px[inb]).astype(int), np.round(py[inb]).astype(int)
    best = (-1, 0, 0)
    for dy in range(-20, 21, 2):
        for dx in range(-20, 21, 2):
            yy, xx = yi0 + dy, xi0 + dx
            ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
            sc = sm[yy[ok], xx[ok]].sum()
            if sc > best[0]:
                best = (sc, dx, dy)
    shift = best[1:]
    # two passes: wide match after the shift, then tight match on the refined model
    q = np.array([p["az0"], p["alt0"], p["roll"], p["f"]])
    for r, sx_, sy_ in ((6, *shift), (3, 0, 0)):
        cm = model(p)
        px, py = cm.project(V)
        meas, keep = [], []
        for i in np.where(inb)[0]:
            c = centroid(img, px[i] + sx_, py[i] + sy_, r, noise)
            if c is not None:
                meas.append(c[:2]); keep.append(i)
        meas, keep = np.array(meas), np.array(keep)

        def resid(qq):
            m = model({**p, "az0": qq[0], "alt0": qq[1], "roll": qq[2], "f": qq[3]})
            x, y = m.project(V[keep])
            return np.concatenate([x - meas[:, 0], y - meas[:, 1]])

        s = least_squares(resid, q, loss="soft_l1", f_scale=1.0)
        q = s.x
        p.update(az0=float(q[0]), alt0=float(q[1]), roll=float(q[2]), f=float(q[3]))
    # local pass: pointing from stars near Saturn only (the planet is measured
    # against its neighbours; the model's weak frame edge drops out)
    cm = model(p)
    sxg, syg = (float(a[0]) for a in cm.project(Vs))
    px, py = cm.project(V)
    for rad in (LOCAL, 1.5 * LOCAL):
        loc = np.where(inb & (np.hypot(px - sxg, py - syg) < rad))[0]
        # local coarse shift first: near the frame edge the global model can be
        # ~20 px out, beyond any match radius
        lx, ly = np.round(px[loc]).astype(int), np.round(py[loc]).astype(int)
        lb = (-1, 0, 0)
        for dy in range(-40, 41):
            for dx in range(-40, 41):
                yy, xx = ly + dy, lx + dx
                ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
                sc = sm[yy[ok], xx[ok]].sum()
                if sc > lb[0]:
                    lb = (sc, dx, dy)
        meas, keep = [], []
        for i in loc:
            c = centroid(img, px[i] + lb[1], py[i] + lb[2], 4, noise)
            if c is not None:
                meas.append(c[:2]); keep.append(i)
        if len(keep) >= 10:
            break
    meas, keep = np.array(meas), np.array(keep)

    def resid_l(qq):
        m = model({**p, "az0": qq[0], "alt0": qq[1], "roll": qq[2]})
        x, y = m.project(V[keep])
        return np.concatenate([x - meas[:, 0], y - meas[:, 1]])

    s = least_squares(resid_l, [p["az0"], p["alt0"], p["roll"]], loss="soft_l1", f_scale=1.0)
    p.update(az0=float(s.x[0]), alt0=float(s.x[1]), roll=float(s.x[2]))
    cm = model(p)
    dx_, dy_ = np.split(s.fun, 2)
    d = np.hypot(dx_, dy_)
    sx, sy = (float(a[0]) for a in cm.project(Vs))
    c = centroid(img, sx, sy, 20, noise, need=20)
    kx, ky = cm.project(V[keep])
    near = np.hypot(kx - sx, ky - sy) < 200
    rec = dict(frame=os.path.basename(path), t_mid=t.isoformat(), shift=list(map(int, shift)),
               n_stars=int(len(keep)), med_px=float(np.median(d)), local_radius=float(rad),
               n_near=int(near.sum()), near_med_px=float(np.median(d[near])) if near.any() else None,
               near_mean_dx=float(np.mean(dx_[near])) if near.any() else None,
               near_mean_dy=float(np.mean(dy_[near])) if near.any() else None,
               az0=p["az0"], alt0=p["alt0"], roll=p["roll"], f=p["f"],
               sat_pred=[sx, sy], sat_ra=float(sat_sc.ra.deg), sat_dec=float(sat_sc.dec.deg))
    if c is None:
        rec["sat_found"] = False
        return rec
    mx, my, snr = c
    rec.update(sat_found=True, sat_meas=[mx, my], sat_peak_sigma=snr,
               sat_dx=mx - sx, sat_dy=my - sy)
    # measured pixel -> sky. Compare as DIRECTIONS (topocentric, apparent): the
    # angle between the measured and the ephemeris unit vectors. RA/Dec are
    # reported in GCRS (apparent geocentric axes) for both - never .icrs, which
    # is barycentric and moves a planet by its annual parallax (~6 deg here).
    v = cm.unproject(np.array([mx]), np.array([my]))[0]
    sep = np.degrees(np.arccos(np.clip(v @ Vs[0], -1, 1))) * 60
    az, alt = np.degrees(np.arctan2(v[0], v[1])) % 360, np.degrees(np.arcsin(v[2]))
    from astropy.coordinates import GCRS
    meas_sc = SkyCoord(AltAz(az=az * u.deg, alt=alt * u.deg, obstime=Time(t), location=LOC, pressure=0)
                       ).transform_to(GCRS(obstime=Time(t)))
    rec.update(meas_ra=float(meas_sc.ra.deg), meas_dec=float(meas_sc.dec.deg),
               eph_ra=float(sat_sc.ra.deg), eph_dec=float(sat_sc.dec.deg), sep_arcmin=float(sep))
    return rec


def main():
    allrec = []
    only = sys.argv[1:]
    for night, a, b in NIGHTS:
        if only and night not in only:
            continue
        fr = frames(night, utc(night, a), utc(night, b))
        print(f"== {night}  {len(fr)} frames {a}-{b} UTC", flush=True)
        # one blind pointing search per night, on the middle frame
        tm, pm = fr[len(fr) // 2]
        img, exp = load(pm)
        noise = 1.4826 * np.median(np.abs(img - np.median(img)))
        p0 = bootstrap(img, tm + timedelta(seconds=exp / 2), dict(P), night)
        for t, path in fr:
            r = fit_frame(t, path, p0)
            r["night"] = night
            allrec.append(r)
            if r["sat_found"]:
                print(f"  {r['t_mid'][11:19]} stars {r['n_stars']:3d} med {r['med_px']:.2f}px  "
                      f"near({r['n_near']}) {r['near_med_px'] or float('nan'):.2f}px  "
                      f"f {r['f']:.1f} Saturn d=({r['sat_dx']:+.2f},{r['sat_dy']:+.2f})px {r['sep_arcmin']:.2f}'  "
                      f"peak {r['sat_peak_sigma']:.0f}sig  at ({r['sat_meas'][0]:.0f},{r['sat_meas'][1]:.0f})",
                      flush=True)
            else:
                print(f"  {r['t_mid'][11:19]} stars {r['n_stars']} med {r['med_px']:.2f}px  Saturn NOT FOUND near "
                      f"({r['sat_pred'][0]:.0f},{r['sat_pred'][1]:.0f})", flush=True)
    json.dump(allrec, open(f"{OUT}/check3{'-' + '_'.join(only) if only else ''}.json", "w"), indent=1)
    # per-night summary and the night-to-night motion, measured vs ephemeris
    print("\n== per night (median over frames)")
    nights = {}
    for n, *_ in NIGHTS:
        rs = [r for r in allrec if r["night"] == n and r["sat_found"]]
        if not rs:
            continue
        nights[n] = dict(
            dx=np.median([r["sat_dx"] for r in rs]), dy=np.median([r["sat_dy"] for r in rs]),
            sep=np.median([r["sep_arcmin"] for r in rs]),
            mra=np.median([r["meas_ra"] for r in rs]), mdec=np.median([r["meas_dec"] for r in rs]),
            era=np.median([r["eph_ra"] for r in rs]), edec=np.median([r["eph_dec"] for r in rs]))
        z = nights[n]
        print(f"  {n}: residual ({z['dx']:+.2f},{z['dy']:+.2f}) px = {z['sep']:.2f}'   "
              f"measured RA {z['mra']:.4f} Dec {z['mdec']:+.4f}   ephem RA {z['era']:.4f} Dec {z['edec']:+.4f}")
    ks = list(nights)
    print("\n== motion between nights (deg): measured vs ephemeris")
    for a, b in zip(ks, ks[1:]):
        A, B = nights[a], nights[b]
        print(f"  {a} -> {b}: dRA meas {B['mra'] - A['mra']:+.3f} eph {B['era'] - A['era']:+.3f}   "
              f"dDec meas {B['mdec'] - A['mdec']:+.3f} eph {B['edec'] - A['edec']:+.3f}")


if __name__ == "__main__":
    main()
