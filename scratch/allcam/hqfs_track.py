"""Does the hqfs model + sidereal rotation follow Polaris through the night? brightest pixel vs prediction."""
import glob, os, sys, numpy as np
from datetime import datetime
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u
sys.path.insert(0, "/home/peter/astro")
from astro.skyglow import CameraModel
cm = CameraModel(os.path.expanduser("~/tmp/allcam/hqfs-cammodel-2026-11-12.json"))
LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg); pol = SkyCoord(37.95456067 * u.deg, 89.26410897 * u.deg)
X = sorted(glob.glob("/mnt/bigstore/astro-data/xoverpi-frames/night/2026-11-12/*/20261112T185923Z-*.fits.fz"), key=os.path.basename)
for p in X[::300]:
    with fits.open(p) as h: d, hd = h[1].data.astype(np.float32), h[1].header
    b = d[:1520, :2028].reshape(760, 2, 1014, 2).sum((1, 3))
    from scipy.ndimage import uniform_filter
    s = uniform_filter(b, 7); y, x = np.unravel_index(np.argmax(s), s.shape)
    t = Time(hd["DATE-OBS"].replace("+00:00", "")) + float(hd["EXPTIME"]) / 2 * u.s
    a = pol.transform_to(AltAz(obstime=t, location=LOC, pressure=0)); al, az = a.alt.rad, a.az.rad
    px, py = cm.project(np.array([np.cos(al) * np.sin(az), np.cos(al) * np.cos(az), np.sin(al)]))
    print(f"{hd['DATE-OBS'][11:19]}  detected ({x:4d},{y:4d})  predicted ({float(px):7.1f},{float(py):7.1f})  d={np.hypot(x - px, y - py):6.1f}px")
