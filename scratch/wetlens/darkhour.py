"""The DARK HOUR of each night: the best contiguous 60-minute window, not tied to clock hours
(astro-deliverables request, Peter 2026-11-25).

From the water/cloud survey (<survey dir>/<night>.npz, one sampled frame per ~10 min) plus hours.csv
(regime + regime_ref_stars) and each night's brightness.csv (frame count).

Window: starts at a sampled frame, covers [start, start + 60 min), needs >= 5 samples inside.
Gates, in order of preference (the first tier with any window wins; its name goes in `gate`):
  astro      sun < -18 and moon < 0 at every sample
  astro-moon sun < -18, Moon up (moonlit; astrocam barely minds the Moon, eclipticam does)
  nautical   sun < -12 and moon < 0 (summer: no astronomical dark at 51.4 N from ~20 May to ~23 Jul)
  nautical-moon  sun < -12
Score: clarity = min sampled star count in the window / regime_ref_stars (as hours.csv), capped at 1.0
for ranking because counts above the regime's best are mostly spurious (lit cloud edges counted as
stars); ties broken by darkness: score = min(clarity, 1) - 0.1 * sky_stops.
sky_stops = log2 of the window's median sky level above black (64 ADU) over the regime's darkest
(5th percentile of astro-gated samples): 0 = as dark as that camera setup gets, 1 = twice as bright.
Flags: water-suspect (regime), blurred (star size > 1.25x regime median), cover-closed (only where the
frame headers record COVER, ~10-18 on), moonNN%, clarity-suspect (clarity > 1.2).
Writes <survey dir>/dark-hours.csv. Usage: darkhour.py <survey dir>"""
import os, sys, glob, csv, json, datetime as dt, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, get_body, get_sun
import astropy.units as u
root = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/astrocam-frames"
sdir = sys.argv[1]; LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg); BLACK = 64.0
WIN = 3600_000; MIN_SAMPLES = 5
hours = list(csv.DictReader(open(f"{sdir}/hours.csv")))
reg = {r["night"]: (r["regime"], float(r["regime_ref_stars"])) for r in hours}
WATER = set(json.load(open(f"{sdir}/regimes.json"))["water"])
TIERS = [("astro", -18, True), ("astro-moon", -18, False), ("nautical", -12, True), ("nautical-moon", -12, False)]

nights = {}
for p in sorted(glob.glob(f"{sdir}/2026-*.npz")):
    night = os.path.basename(p)[:-4]
    if night not in reg: continue
    T = np.load(p)["table"]
    if len(T) < MIN_SAMPLES: continue
    tm = Time(T[:, 0] / 1000, format="unix"); fr = AltAz(obstime=tm, location=LOC)
    mb = get_body("moon", tm, LOC)
    illum = (1 - np.cos(np.radians(get_sun(tm).separation(mb).deg))) / 2
    nights[night] = dict(T=T, sun=get_sun(tm).transform_to(fr).alt.deg, moon=mb.transform_to(fr).alt.deg, illum=illum)

# regime darkness reference and star-size reference, from astro-gated samples
lev, size = {}, {}
for n, d in nights.items():
    g = (d["sun"] < -18) & (d["moon"] < 0); rg = reg[n][0]
    lev.setdefault(rg, []).extend(d["T"][g, 20] - BLACK)
    size.setdefault(rg, []).extend(np.nanmedian(d["T"][:, 11:20], 1))
dark_ref = {rg: max(float(np.percentile(v, 5)), 1.0) for rg, v in lev.items() if len(v) >= 20}
size_ref = {rg: float(np.nanmedian(v)) for rg, v in size.items()}

def frames_in(night, a, b):
    bf = f"{root}/{night}/brightness.csv"
    if not os.path.exists(bf): return ""
    n = 0
    for r in csv.DictReader(open(bf)):
        try: t = int(r["epoch_ms"])
        except (KeyError, ValueError): continue
        n += a <= t < b
    return n

rows = []
for night, d in sorted(nights.items()):
    T, rg, ref = d["T"], *reg[night]
    lv = T[:, 20] - BLACK
    dref = dark_ref.get(rg) or max(float(np.percentile(lv, 5)), 1.0)
    best = None
    for tier, sun_max, moon_down in TIERS:
        ok = (d["sun"] < sun_max) & ((d["moon"] < 0) if moon_down else True)
        for i in range(len(T)):
            j = np.nonzero((T[:, 0] >= T[i, 0]) & (T[:, 0] < T[i, 0] + WIN))[0]
            if len(j) < MIN_SAMPLES or not ok[j].all(): continue
            clar = T[j, 1].min() / ref
            stops = float(np.log2(max(np.median(lv[j]), 0.5) / dref))
            score = min(clar, 1.0) - 0.1 * stops
            if best is None or score > best[0]: best = (score, tier, i, j, clar, stops)
        if best: break
    if not best: continue
    score, tier, i, j, clar, stops = best
    a, b = int(T[i, 0]), int(T[i, 0]) + WIN
    fl = []
    if rg in WATER: fl.append("water-suspect")
    sz = np.nanmedian(T[j, 11:20])
    if np.isfinite(sz) and sz > 1.25 * size_ref.get(rg, np.inf): fl.append("blurred")
    if T[:, 23].max() > 0 and np.mean(T[j, 23]) < 0.5: fl.append("cover-closed")   # COVER header only from ~10-18; absent reads 0
    if d["moon"][j].max() > 0: fl.append(f"moon{int(d['illum'][j].mean() * 100)}%")
    if T[j, 1].min() / ref > 1.2: fl.append("clarity-suspect")
    rows.append(dict(night=night, start_utc=dt.datetime.fromtimestamp(a / 1000, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     end_utc=dt.datetime.fromtimestamp(b / 1000, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     start_ms=a, end_ms=b, gate=tier, clarity=round(clar, 3), sky_stops=round(stops, 2), score=round(score, 3),
                     n_frames=frames_in(night, a, b), n_samples=len(j), stars_min=int(T[j, 1].min()), regime_ref_stars=int(ref),
                     sun_alt_max=round(float(d["sun"][j].max()), 1), moon_alt_max=round(float(d["moon"][j].max()), 1),
                     regime=rg, flags=" ".join(fl)))
with open(f"{sdir}/dark-hours.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "nights ->", f"{sdir}/dark-hours.csv")
