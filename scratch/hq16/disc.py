"""Defocus blur discs for HQ16: forward-model each star as a defocused disc swept along its
60 s trail, and turn its diameter into defocus at the sensor.

Model per star (2x2 binned, 3.1 um px): a disc of radius R whose brightness varies as
1 + k*(2(r/R)^2 - 1) (k > 0 bright rim, k < 0 bright centre: the spherical-aberration
signature that differs inside and outside focus), swept a length L at angle th (the trail),
blurred by a Gaussian sigma (in-focus PSF + seeing), plus a constant. Fitted to an 81 px cutout.

Defocus at the sensor: delta = D * N (D = blur diameter, N = f-number, infinity object).
Then a plane delta(x, y) = a + b*x + c*y over the field gives tilt.

Env: NIGHT (default 2026-11-02), HOURS (default "02"), STEP (default 1), N_F (f-number, 1.4),
MAXF (cap on frames, default 0 = all). Writes ~/tmp/hq16-disc-<NIGHT>.npy and a PNG of
example fits ~/tmp/hq16-disc-<NIGHT>.png. Run on muppet (frames on bigstore).
"""
import glob, os, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from scipy.ndimage import gaussian_filter
from scipy.optimize import least_squares

NIGHT = os.environ.get("NIGHT", "2026-11-02")
HOURS = os.environ.get("HOURS", "02").split()
STEP = int(os.environ.get("STEP", "1"))
NF = float(os.environ.get("N_F", "1.4"))
MAXF = int(os.environ.get("MAXF", "0"))
PX_UM = 3.1                      # binned pixel (2 x 1.55 um)
H, W = 1520, 2028
BAND_Y = 1350                    # bright band along the bottom edge: excluded
HW = 40                          # cutout half-width
R0 = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/eclipticam-frames/night/" + NIGHT + "/hq16"
files = sorted(f for h in HOURS for f in glob.glob(R0 + "/" + h + "/*.fits.fz"))[::STEP]
if MAXF: files = files[:MAXF]

yy, xx = np.mgrid[-HW:HW + 1, -HW:HW + 1].astype(np.float32)

def model(p):
    a, x0, y0, th, L, R, k, s, c = p
    img = np.zeros_like(xx)
    ux, uy = np.cos(th), np.sin(th)
    n = max(3, int(L) + 1)
    for t in np.linspace(-L / 2, L / 2, n):
        r = np.hypot(xx - x0 - t * ux, yy - y0 - t * uy)
        inside = np.clip(R - r + 0.5, 0, 1)                 # anti-aliased edge
        img += inside * (1 + k * (2 * np.clip(r / R, 0, 1) ** 2 - 1))
    img /= n
    if s > 0.3: img = gaussian_filter(img, s)
    return a * img + c

def fit(cut, th0, L0, R0_):
    p0 = [cut.max(), 0, 0, th0, L0, R0_, 0.0, 1.0, 0.0]
    lo = [0, -8, -8, th0 - 0.4, 1, 1.5, -0.9, 0.3, -np.inf]
    hi = [np.inf, 8, 8, th0 + 0.4, 70, 38, 0.9, 4.0, np.inf]
    r = least_squares(lambda p: (model(p) - cut).ravel(), p0, bounds=(lo, hi),
                      x_scale=[max(cut.max(), 1), 1, 1, .1, 3, 2, .2, .5, 5], max_nfev=400)
    return r

rows, examples = [], []
for fi, f in enumerate(files):
    d = fits.getdata(f, 1).astype(np.float32) - 256
    b = d[0::2, 0::2] + d[0::2, 1::2] + d[1::2, 0::2] + d[1::2, 1::2]
    r = b - Background2D(b, (64, 64), filter_size=(3, 3), bkg_estimator=MedianBackground()).background
    _, _, sd = sigma_clipped_stats(r)
    sm = gaussian_filter(r, 3)
    _, _, sds = sigma_clipped_stats(sm)
    seg = detect_sources(sm, 4 * sds, n_pixels=60)
    if seg is None: continue
    for s in SourceCatalog(r, seg, convolved_data=sm):
        x, y = float(s.xcentroid), float(s.ycentroid)
        if not (HW + 2 < x < W - HW - 2 and HW + 2 < y < BAND_Y): continue
        if s.max_value > 12000: continue                     # near saturation
        xi, yi = int(round(x)), int(round(y))
        cut = r[yi - HW:yi + HW + 1, xi - HW:xi + HW + 1]
        th0 = np.deg2rad(s.orientation.value)
        a_, b_ = s.semimajor_axis.value, s.semiminor_axis.value
        R_ = float(np.clip(2 * b_, 2, 30)); L_ = float(np.clip(2 * (a_ - b_) * 2, 2, 60))
        try: q = fit(cut, th0, L_, R_)
        except Exception: continue
        p = q.x
        res = q.fun.reshape(cut.shape)
        snr = p[0] * np.pi * p[5] ** 2 / (sd * np.sqrt(np.pi * p[5] ** 2 + 2 * p[5] * p[4]))
        chi = np.std(res) / sd
        if snr < 15 or chi > 1.6 or p[5] >= 37.5 or abs(p[1]) > 7 or abs(p[2]) > 7: continue
        D = 2 * p[5]
        rows.append((xi + p[1], yi + p[2], D, D * PX_UM, D * PX_UM * NF, p[4], p[6], p[7], snr, chi, fi, np.rad2deg(p[3])))
        if len(examples) < 6 and snr > 40 and 12 < p[4] < 30: examples.append((cut, model(p), res, D, p[6]))
    print(f"{fi + 1}/{len(files)} {os.path.basename(f)} stars so far {len(rows)}", flush=True)

rows = np.array(rows)
LMIN, LMAX = float(os.environ.get("LMIN", "12")), float(os.environ.get("LMAX", "30"))
nall = len(rows)
if nall: rows = rows[(rows[:, 5] > LMIN) & (rows[:, 5] < LMAX)]   # star trails only: drops blends/gradients
np.save(os.path.expanduser(f"~/tmp/hq16-disc-{NIGHT}.npy"), rows)
cols = "x y D_px D_um delta_um L k sigma snr chi frame th_deg"
print("\ncolumns:", cols)
print(f"{len(files)} frames, {nall} fits, {len(rows)} kept with trail {LMIN:.0f}-{LMAX:.0f} px")
if len(rows):
    for name, j in [("D binned px", 2), ("D um", 3), ("defocus um (D*N)", 4), ("trail L px", 5),
                    ("rim k", 6), ("sigma px", 7), ("snr", 8)]:
        v = rows[:, j]; print(f"  {name:18s} median {np.median(v):7.2f}  p16 {np.percentile(v,16):7.2f}  p84 {np.percentile(v,84):7.2f}")
    # plane fit of defocus across the field (um), x/y measured from the centre in mm on the sensor
    X = (rows[:, 0] - W / 2) * PX_UM / 1000; Y = (rows[:, 1] - H / 2) * PX_UM / 1000
    A = np.c_[np.ones_like(X), X, Y]; dlt = rows[:, 4]
    w = np.ones_like(dlt)
    for _ in range(5):                                       # iteratively clipped least squares
        sol, *_ = np.linalg.lstsq(A * w[:, None], dlt * w, rcond=None)
        e = dlt - A @ sol; m = np.median(np.abs(e)) * 1.4826; w = (np.abs(e) < 3 * m).astype(float)
    print(f"\nplane: defocus = {sol[0]:.1f} um at centre {sol[1]:+.1f} um/mm in x (right) {sol[2]:+.1f} um/mm in y (down)")
    print(f"  tilt across sensor: x {np.degrees(np.arctan(sol[1]/1000))*60:+.1f} arcmin, y {np.degrees(np.arctan(sol[2]/1000))*60:+.1f} arcmin;"
          f" scatter {m:.1f} um; used {int(w.sum())}/{len(w)}")
    print(f"  corners (um): TL {sol@[1,-3.14,-2.36]:.0f}  TR {sol@[1,3.14,-2.36]:.0f}  BL {sol@[1,-3.14,2.36]:.0f}  BR {sol@[1,3.14,2.36]:.0f}")
    nx, ny = 4, 3
    print("\nmedian defocus um on a 4x3 grid (n), top row first:")
    for jj in range(ny):
        line = []
        for ii in range(nx):
            k = (rows[:, 0] // (W / nx) == ii) & (rows[:, 1] // (BAND_Y / ny) == jj)
            line.append(f"{np.median(rows[k,4]):5.0f}({k.sum():3d})" if k.sum() >= 3 else f"  -  ({k.sum():3d})")
        print("  ".join(line))

if examples:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(len(examples), 3, figsize=(7.5, 2.5 * len(examples)), facecolor="black")
    ax = np.atleast_2d(ax)
    for i, (c, mo, re, D, k) in enumerate(examples):
        v = np.percentile(c, 99.5)
        for j, (im, t) in enumerate([(c, "data"), (mo, f"model D={D:.1f}px={D*PX_UM:.0f}um k={k:+.2f}"), (re, "residual")]):
            a = ax[i, j]; a.imshow(im, cmap="gray", vmin=-0.2 * v, vmax=v, origin="upper"); a.set_axis_off()
            a.set_title(t, color="#E0E0E0", fontsize=7)
            a.plot([4, 4 + 10], [76, 76], color="#FF9500", lw=2)                       # scale bar
            a.text(4, 73, "10 px = 31 um = 6.6'", color="#FF9500", fontsize=6)
    fig.suptitle(f"HQ16 {NIGHT} blur discs (2x2 binned; bar 10 px = 31 um on sensor = 6.6 arcmin)", color="#E0E0E0", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.expanduser(f"~/tmp/hq16-disc-{NIGHT}.png"), dpi=110, facecolor="black")
