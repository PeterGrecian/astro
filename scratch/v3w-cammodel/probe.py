"""Star count per night (epoch 7): pointing-only refine of the 10-07 model on one frame per night."""
import os, sys, math, warnings
os.environ["STARS_ALLSKY"] = "1"
import numpy as np
from datetime import timedelta
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import check3
from check3 import STARS, P, enu_of
import importlib.util
from astropy.coordinates import SkyCoord, get_body, AltAz
from astropy.time import Time
import astropy.units as u
spec = importlib.util.spec_from_file_location("se", os.path.expanduser("~/astro/scratch/saturn-walk/scan-epochs.py"))
se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
SC = SkyCoord(STARS[:, 0] * u.deg, STARS[:, 1] * u.deg)
for night in sys.argv[1:]:
    for hm in ("23:30", "01:00", "02:30"):
        fr = check3.frames(night, check3.utc(night, hm), check3.utc(night, hm) + timedelta(minutes=3))
        if not fr: print(night, hm, "no frame", flush=True); continue
        t, path = fr[0]
        img, exp = check3.load(path)
        noise = 1.4826 * np.median(np.abs(img - np.median(img)))
        V = enu_of(SC, t + timedelta(seconds=exp / 2))
        n, med, p = se.refine(img, noise, V, dict(P))
        moon = get_body("moon", Time(t)).transform_to(AltAz(obstime=Time(t), location=check3.LOC)).alt.deg
        print(f"{night} {hm} n_good {n:3d} median {med:5.2f} px  noise {noise:6.1f}  moon alt {moon:+5.1f}", flush=True)
