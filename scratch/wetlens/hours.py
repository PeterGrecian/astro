"""Every astrocam hour of every night: sky brightness, star count, Sun and Moon. For ranking cloudless hours.
Brightness from each night's brightness.csv (all frames); star count from the water survey
(<survey dir>/<night>.npz, one frame per 10 min). Writes <survey dir>/hours.csv.
Usage: hours.py <survey dir>"""
import os, sys, glob, csv, datetime, numpy as np, warnings
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
                hrs.setdefault(t.replace(minute=0, second=0, microsecond=0), {"med": [], "exp": [], "open": [], "stars": []})
                h = hrs[t.replace(minute=0, second=0, microsecond=0)]
                h["med"].append(float(r["median"])); h["exp"].append(ex); h["open"].append(r.get("cover", "") != "closed")
            except Exception: pass
    sf = f"{sdir}/{night}.npz"
    if os.path.exists(sf):
        T = np.load(sf)["table"]
        for row in T:
            t = datetime.datetime.fromtimestamp(row[0] / 1000, datetime.UTC).replace(minute=0, second=0, microsecond=0)
            hrs.setdefault(t, {"med": [], "exp": [], "open": [], "stars": []})["stars"].append(row[1])
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
                         sun_alt=round(float(sa), 1), moon_alt=round(float(ma), 1), moon_illum=round(float(il), 2)))
with open(f"{sdir}/hours.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "hours ->", f"{sdir}/hours.csv")
