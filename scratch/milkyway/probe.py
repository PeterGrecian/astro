"""Which named stars / galactic-plane points land in astrocam's 10-07 frame at 23:05:39 UTC."""
import sys, numpy as np, warnings
sys.path.insert(0, "/home/peter/astro")
sys.argv = ["x"]
warnings.filterwarnings("ignore")
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
from astropy.time import Time
import astropy.units as u
from astro.skyglow import CameraModel, _enu
D = "/mnt/muppet/bigstore/astrocam-frames/2026-10-07/"
cm = CameraModel(D + "skyglow-cammodel-night.json")
T = Time("2026-10-07T23:06:09")   # mid-exposure of the 23:05:39 frame
loc = EarthLocation(lat=51.3948*u.deg, lon=-0.2923*u.deg)
def pix(c):
    aa = c.transform_to(AltAz(obstime=T, location=loc, pressure=0))
    return cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
names = ["Polaris","Kochab","Dubhe","Merak","Megrez","Alioth","Caph","Schedar","Navi","Ruchbah","Segin",
         "Mirfak","Algol","Capella","Menkalinan","Alderamin","Errai","Deneb","Vega","Thuban","Eltanin"]
for n in names:
    try: c = SkyCoord.from_name(n)
    except Exception as e: print(n, "?"); continue
    x, y = pix(c); print(f"{n:10s} {c.ra.deg:8.3f} {c.dec.deg:7.3f}  {float(x):7.1f} {float(y):7.1f}")
for n, ra, dec in [("DoubleCl", 34.75, 57.13), ("Mel20", 51.68, 49.0), ("M31", 10.68, 41.27), ("M103",23.34,60.65)]:
    x, y = pix(SkyCoord(ra*u.deg, dec*u.deg)); print(f"{n:10s} {float(x):7.1f} {float(y):7.1f}")
l = np.arange(0, 360, 5.)
x, y = pix(SkyCoord(l=l*u.deg, b=0*u.deg, frame=Galactic))
for li, xi, yi in zip(l, x, y):
    if -200 < xi < 2500 and -200 < yi < 1500: print("l", li, round(float(xi)), round(float(yi)))
