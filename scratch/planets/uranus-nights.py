import json, sys
import numpy as np
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "/home/peter/astro/scratch/saturn-walk")
from check3 import model, _enu
from astropy.coordinates import AltAz, EarthLocation, get_body
from astropy.time import Time
import astropy.units as u
P = json.load(open("/home/peter/astro/eclipticam-v3w/cammodel-2026-10-07.json")); M = model(P)
LOC = EarthLocation(lat=P["lat"] * u.deg, lon=P["lon"] * u.deg)
W, H = 2304, 1296
for d in range(0, 90, 3):
    base = datetime(2026, 7, 15, 12, tzinfo=timezone.utc) + timedelta(days=d)
    ts = Time([base + timedelta(minutes=5 * i) for i in range(288)])
    aa = AltAz(obstime=ts, location=LOC, pressure=0)
    s = get_body("sun", ts, LOC).transform_to(aa); b = get_body("uranus", ts, LOC); ba = b.transform_to(aa)
    x, y = M.project(_enu(np.radians(ba.az.deg), np.radians(ba.alt.deg)))
    ok = (ba.alt.deg > 20) & (s.alt.deg < -12) & (x > 150) & (x < W - 150) & (y > 100) & (y < H - 150)
    i = np.where(ok)[0]
    g = b.transform_to("gcrs")
    print(f"{base:%Y-%m-%d} {ok.sum()*5/60:4.1f} h  RA {g.ra.deg[144]:.3f} Dec {g.dec.deg[144]:+.3f}",
          f"{ts[i[0]].datetime:%H:%M}-{ts[i[-1]].datetime:%H:%M}" if len(i) else "")
