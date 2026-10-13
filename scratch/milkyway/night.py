"""Where the Milky Way's stars sit in astrocam's frame through the night of 10-07, and whether they are on open sky."""
import sys, json, warnings, numpy as np
sys.path.insert(0, "/home/peter/astro"); warnings.filterwarnings("ignore")
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time
import astropy.units as u
from astro.skyglow import CameraModel, GlowModel, _enu
D = "/mnt/muppet/bigstore/astrocam-frames/2026-10-07/"
cm = CameraModel(D + "skyglow-cammodel-night.json")
gm = GlowModel(D + "skyglow-model.npz")
mask = gm.sky_mask((1296, 2304), erode=2)
loc = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
OBJ = {"Caph": (2.295, 59.150), "Ruchbah": (21.454, 60.235), "DoubleCl": (34.75, 57.13), "Mirfak": (51.081, 49.861), "Deneb": (310.358, 45.28)}
c = SkyCoord([v[0] for v in OBJ.values()] * u.deg, [v[1] for v in OBJ.values()] * u.deg)
print("BST    " + "  ".join(f"{k:>16s}" for k in OBJ))
for h in np.arange(19.5, 29.6, 0.5):   # UTC hours from 7 Oct 00:00
    T = Time("2026-10-07T00:00:00") + h * u.hour
    aa = c.transform_to(AltAz(obstime=T, location=loc, pressure=0))
    x, y = cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    row = []
    for xi, yi, alt in zip(x, y, aa.alt.deg):
        ins = 0 <= xi < 2304 and 0 <= yi < 1296
        st = ("sky" if mask[int(yi), int(xi)] else "MASK") if ins else "out"
        row.append(f"{int(xi):5d},{int(yi):5d} {st:4s}")
    bst = (h + 1) % 24
    print(f"{int(bst):02d}:{int(bst%1*60):02d}  " + "  ".join(row))
