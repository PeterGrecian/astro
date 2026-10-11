"""Local astrometry for Saturn: astrometry.net on a crop centred on the planet
(planet masked out of the solve), SIP order 3, Saturn's trail centroid -> RA/Dec
through that WCS, compared with ephem's astrometric J2000 place (same frame as
the Tycho-2 index stars, so aberration cancels locally)."""
import glob, os, subprocess, sys, tempfile, warnings
from datetime import datetime, timezone, timedelta
import numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/astro/scratch/saturn-walk"))
import check3, ephem
from astropy.io import fits
from astropy.wcs import WCS

# (night, time, approximate Saturn pixel: from check3 / by eye on the 02:50 frame)
CASES = [("2026-07-27", "02:50", (246, 336)), ("2026-07-27", "02:57", (300, 345)), ("2026-07-27", "03:02", (329, 352)),
         ("2026-07-26", "03:01", (330, 352)), ("2026-09-05", "01:13", (697, 368)), ("2026-10-07", "23:33", (857, 456))]
for night, hm, hint in CASES:
    t0 = check3.utc(night, hm)
    ps = glob.glob(f"{check3.BASE}/{night}/v3w/*/*.fits.fz")
    ts = [(abs(datetime.fromtimestamp(int(os.path.basename(p)[:13]) / 1000, timezone.utc) - t0), p) for p in ps]
    p = min(ts)[1]
    t = datetime.fromtimestamp(int(os.path.basename(p)[:13]) / 1000, timezone.utc)
    img, exp = check3.load(p)
    tm = t + timedelta(seconds=exp / 2)
    noise = 1.4826 * np.median(np.abs(img - np.median(img)))
    # locate Saturn: brightest blob in the frame's sky half near where the night's runs found it
    from scipy.ndimage import maximum_filter
    H, W = img.shape
    o = ephem.Observer(); o.lat, o.lon = str(check3.P["lat"]), str(check3.P["lon"]); o.date = ephem.Date(tm.replace(tzinfo=None)); o.pressure = 0
    s = ephem.Saturn(o)
    c = check3.centroid(img, hint[0], hint[1], 30, noise, need=20)
    if c is None:
        print(night, hm, "no saturn blob"); continue
    sx, sy = c[0], c[1]
    x0, y0 = int(np.clip(sx - 260, 0, W - 520)), int(np.clip(sy - 220, 0, H - 440))
    cut = img[y0:y0 + 440, x0:x0 + 520].copy()
    yy, xx = np.mgrid[:cut.shape[0], :cut.shape[1]]
    cut[np.hypot(xx - (sx - x0), yy - (sy - y0)) < 15] = 0          # planet out of the solve
    wd = tempfile.mkdtemp(prefix=f"crop-{night}-", dir=check3.OUT)
    fn = f"{wd}/c.fits"
    fits.PrimaryHDU(np.nan_to_num(cut).clip(-50, None).astype(np.float32)).writeto(fn)
    subprocess.run(["solve-field", fn, "--overwrite", "--no-plots", "--scale-units", "arcsecperpix",
                    "--scale-low", "60", "--scale-high", "320", "--cpulimit", "90", "--objs", "120",
                    "--tweak-order", "3", "--crpix-center"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(f"{wd}/c.wcs"):
        print(f"{night} {hm}: crop at ({x0},{y0}) did not solve; Saturn blob at ({sx:.0f},{sy:.0f}) {c[2]:.0f} sigma"); continue
    w = WCS(fits.getheader(f"{wd}/c.wcs"))
    ra, dec = w.all_pix2world([[sx - x0, sy - y0]], 0)[0]
    with fits.open(f"{wd}/c.corr") as h:
        cc = h[1].data
        rx, ry = w.all_world2pix(np.c_[cc["index_ra"], cc["index_dec"]], 0).T
        rr = np.hypot(rx - (cc["field_x"] - 1), ry - (cc["field_y"] - 1))
    era, edec = np.degrees(s.a_ra), np.degrees(s.a_dec)
    dra = (ra - era) * np.cos(np.radians(edec)) * 60; ddec = (dec - edec) * 60
    print(f"{night} {tm:%H:%M:%S} Saturn ({sx:.0f},{sy:.0f}) {c[2]:.0f}sig | crop solve {len(cc)} stars, "
          f"median resid {np.median(rr):.2f}px | meas RA {ra:.4f} Dec {dec:+.4f}  ephem RA {era:.4f} Dec {edec:+.4f} "
          f"| off dRA*cos {dra:+.2f}' dDec {ddec:+.2f}' = {np.hypot(dra, ddec):.2f}'", flush=True)
