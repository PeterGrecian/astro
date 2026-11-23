"""Every astrocam hour of every night: sky brightness, star count, Sun and Moon. For ranking cloudless hours.
Brightness from each night's brightness.csv (all frames); star count from the water survey
(<survey dir>/<night>.npz, one frame per 10 min). Writes <survey dir>/hours.csv (by time), hours-ranked.csv (by clarity), regimes.json.
clarity = the hour's WORST sampled star count / the 95th percentile of moonless astro-dark hours in its regime,
so 1.0 = as clear as the best hours that camera setup ever had, all hour long.
Usage: hours.py <survey dir>"""
import os, sys, glob, csv, json, datetime, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, get_body, get_sun
import astropy.units as u
root = os.environ.get("BIGSTORE", "/mnt/bigstore/astro-data") + "/astrocam-frames"
sdir = sys.argv[1]; LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
rows = []
for night in sorted(os.path.basename(p) for p in glob.glob(f"{root}/2026-*")):
    hrs = {}
    bf = f"{root}/{night}/brightness.csv"
    if os.path.exists(bf):
        for r in csv.DictReader(open(bf)):
            try:
                t = datetime.datetime.fromisoformat(r["iso_utc"]); ex = float(r["exptime"] or "nan")
                hrs.setdefault(t.replace(minute=0, second=0, microsecond=0), {"med": [], "exp": [], "open": [], "stars": [], "size": []})
                h = hrs[t.replace(minute=0, second=0, microsecond=0)]
                h["med"].append(float(r["median"])); h["exp"].append(ex); h["open"].append(r.get("cover", "") != "closed")
            except Exception: pass
    sf = f"{sdir}/{night}.npz"
    if os.path.exists(sf):
        T = np.load(sf)["table"]
        for row in T:
            t = datetime.datetime.fromtimestamp(row[0] / 1000, datetime.UTC).replace(minute=0, second=0, microsecond=0)
            hh = hrs.setdefault(t, {"med": [], "exp": [], "open": [], "stars": [], "size": []}); hh["stars"].append(row[1])
            if np.isfinite(row[11:20]).sum() >= 5: hh["size"].append(np.nanmedian(row[11:20]))
    if not hrs: continue
    keys = sorted(hrs); tm = Time([k + datetime.timedelta(minutes=30) for k in keys])
    fr = AltAz(obstime=tm, location=LOC)
    sun = get_sun(tm).transform_to(fr).alt.deg; mb = get_body("moon", tm, LOC); moon = mb.transform_to(fr).alt.deg
    elong = get_sun(tm).separation(mb).deg; illum = (1 - np.cos(np.radians(elong))) / 2
    for k, sa, ma, il in zip(keys, sun, moon, illum):
        h = hrs[k]
        rows.append(dict(night=night, hour=k.strftime("%Y-%m-%dT%H"), nframes=len(h["med"]),
                         sky_median=round(float(np.median(h["med"])), 1) if h["med"] else "",
                         exptime=round(float(np.nanmedian(h["exp"])), 1) if h["exp"] else "",
                         open_frac=round(float(np.mean(h["open"])), 2) if h["open"] else "",
                         stars=round(float(np.median(h["stars"])), 0) if h["stars"] else "",
                         stars_min=round(float(np.min(h["stars"])), 0) if h["stars"] else "",
                         star_size=round(float(np.median(h["size"])), 2) if h["size"] else "",
                         sun_alt=round(float(sa), 1), moon_alt=round(float(ma), 1), moon_illum=round(float(il), 2)))
# ---- rank: each hour against the best dark hours of its own regime (camera epoch / exposure / cover / water)
REGIMES = [("E1-av2", "2026-06-01", "2026-07-28"), ("E2-av3s", "2026-07-29", "2026-08-19"),
           ("E3-window-60s", "2026-08-20", "2026-10-08"), ("E3-window-15s", "2026-10-09", "2026-10-16"),
           ("E4-refit", "2026-10-17", "2026-10-17"), ("E5-zenith", "2026-10-18", "2026-10-24"),
           ("E6-water-ring", "2026-10-25", "2026-10-27"), ("E7-no-cover-storm", "2026-10-28", "2026-11-11"),
           ("E8-washed", "2026-11-12", "2099-01-01")]
WATER = {"E6-water-ring": "dried water ring at (2622,473) from the wet night 10-22/23",
         "E7-no-cover-storm": "storm 10-27/28 blew the cover off; water on the lens",
         "E8-washed": "camera washed 11-12; Peter saw a watermark on 13-14 Nov"}
def regime(n): return next(r for r, a, b in REGIMES if a <= n <= b)
for r in rows: r["regime"] = regime(r["night"])
for reg in {r["regime"] for r in rows}:
    rs = [r for r in rows if r["regime"] == reg]
    dark = [r["stars"] for r in rs if r["stars"] != "" and r["sun_alt"] < -18 and r["moon_alt"] < 0]
    ref = float(np.percentile(dark, 95)) if len(dark) >= 5 else float(np.percentile([r["stars"] for r in rs if r["stars"] != ""] or [1], 95))
    sz = [r["star_size"] for r in rs if r["star_size"] != ""]; szref = float(np.median(sz)) if sz else np.nan
    for r in rs:
        r["regime_ref_stars"] = round(ref, 0)
        r["clarity"] = round(min(1.5, r["stars_min"] / ref), 3) if r["stars_min"] != "" else ""
        fl = []
        if r["sun_alt"] > -18: fl.append("twilight")
        if r["moon_alt"] > 0: fl.append(f"moon{int(r['moon_illum'] * 100)}%")
        if r["star_size"] != "" and np.isfinite(szref) and r["star_size"] > 1.25 * szref: fl.append("blurred")
        if reg in WATER: fl.append("water-suspect")
        if r["open_frac"] != "" and r["open_frac"] < 0.5: fl.append("cover-closed")
        r["flags"] = " ".join(fl)
rows.sort(key=lambda r: r["hour"])
with open(f"{sdir}/hours.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
rk = sorted([r for r in rows if r["clarity"] != ""], key=lambda r: -r["clarity"])
for i, r in enumerate(rk, 1): r["rank"] = i
with open(f"{sdir}/hours-ranked.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rk[0])); w.writeheader(); w.writerows(rk)
json.dump(dict(regimes=REGIMES, water=WATER), open(f"{sdir}/regimes.json", "w"), indent=1)
print(len(rows), "hours ->", f"{sdir}/hours.csv, hours-ranked.csv, regimes.json")
