#!/usr/bin/env python3
"""When are Mars, Jupiter, Uranus (and Saturn, Neptune for reference) inside
eclipticam v3w's frame in the dark, Oct 2026 - May 2027? Uses the 10-07 camera
model. Prints per 10-day step: hours in frame with Sun < -12, RA/Dec, mag-ish
size, elongation."""
import json, sys
import numpy as np
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "/home/peter/astro/scratch/saturn-walk")
from check3 import model, _enu                                     # noqa: E402
from astropy.coordinates import AltAz, EarthLocation, get_body, get_sun   # noqa: E402
from astropy.time import Time                                      # noqa: E402
import astropy.units as u                                          # noqa: E402

P = json.load(open("/home/peter/astro/eclipticam-v3w/cammodel-2026-10-07.json"))
M = model(P)
LOC = EarthLocation(lat=P["lat"] * u.deg, lon=P["lon"] * u.deg)
W, H = 2304, 1296
DIAM = {"mars": 6779, "jupiter": 139820, "uranus": 50724, "saturn": 116460, "neptune": 49244}
t0 = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
for body in ["mars", "jupiter", "uranus", "saturn", "neptune"]:
    print(f"== {body}")
    for d in range(0, 220, 14):
        base = t0 + timedelta(days=d)
        ts = Time([base + timedelta(minutes=10 * i) for i in range(144)])
        aa = AltAz(obstime=ts, location=LOC, pressure=0)
        s = get_sun(ts).transform_to(aa)
        b = get_body(body, ts, LOC)
        ba = b.transform_to(aa)
        x, y = M.project(_enu(np.radians(ba.az.deg), np.radians(ba.alt.deg)))
        inf = (x > 0) & (x < W) & (y > 0) & (y < H) & (s.alt.deg < -12) & (ba.alt.deg > 5)
        dark_up = (s.alt.deg < -12) & (ba.alt.deg > 15)
        size = 2 * np.degrees(np.arctan(DIAM[body] / 2 / b.distance.km[72])) * 3600
        el = b[72].separation(get_sun(ts[72])).deg
        print(f"  {base:%Y-%m-%d}  in frame {inf.sum()/6:4.1f} h  up>15 dark {dark_up.sum()/6:4.1f} h  "
              f"RA {b.ra.deg[72]/15:5.2f}h Dec {b.dec.deg[72]:+6.1f}  {size:5.1f}\"  elong {el:5.1f}")
