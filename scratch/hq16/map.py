"""FWHM map across the HQ16 field: pool the cross-trail widths from fwhm.py's
method over the clear 03:00-05:20 UTC frames, median on a 6x4 grid."""
import glob, os, sys, numpy as np, warnings, json
warnings.filterwarnings("ignore")
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from scipy.ndimage import rotate, gaussian_filter
from scipy.optimize import curve_fit
R = os.environ["BIGSTORE"] + "/eclipticam-frames/night/2026-10-13/hq16"
files = sorted(glob.glob(R + "/0[345]/*.fits.fz"))[::4]
g = lambda x,a,m,s,c: a*np.exp(-.5*((x-m)/s)**2)+c
rows = []
for f in files:
    d = fits.getdata(f, 1).astype(np.float32) - 256
    b = d[0::2,0::2]+d[0::2,1::2]+d[1::2,0::2]+d[1::2,1::2]
    r = b - Background2D(b,(64,64),filter_size=(3,3),bkg_estimator=MedianBackground()).background
    _,_,sd = sigma_clipped_stats(r)
    seg = detect_sources(gaussian_filter(r,1), 5*sd, n_pixels=20)
    if seg is None: continue
    for s in SourceCatalog(r, seg):
        x,y,th,L = int(s.x_centroid), int(s.y_centroid), s.orientation.value, s.semimajor_axis.value
        if s.max_value > 13000 or L < 2*s.semiminor_axis.value: continue
        cut = r[y-20:y+21, x-20:x+21]
        if cut.shape != (41,41): continue
        p = rotate(cut, th, reshape=False, order=1)[:, 20-int(L):20+int(L)+1].mean(1)
        try: q,_ = curve_fit(g, np.arange(41), p, p0=[p.max(),20,1.5,0])
        except Exception: continue
        if not (0.3 < abs(q[2]) < 6 and abs(q[1]-20) < 3 and q[0] > 20*sd/np.sqrt(2*int(L)+1)): continue
        rows.append((x, y, 2.3548*abs(q[2]), q[0]))
rows = np.array(rows); H, W = 1520, 2028
np.save(os.path.expanduser("~/tmp/hq16-map-rows.npy"), rows)
nx, ny = 6, 4
m = np.full((ny, nx), np.nan); n = np.zeros((ny, nx), int)
for j in range(ny):
    for i in range(nx):
        k = (rows[:,0]//(W/nx) == i) & (rows[:,1]//(H/ny) == j)
        n[j,i] = k.sum()
        if k.sum() >= 5: m[j,i] = np.median(rows[k,2])
print(len(files), "frames,", len(rows), "stars; overall median", np.median(rows[:,2]))
print("median cross-trail FWHM, binned px (39.8\"), rows top->bottom:")
for j in range(ny): print("  ".join(f"{v:4.1f}({c:3d})" for v, c in zip(m[j], n[j])))
print("best decile:", np.percentile(rows[:,2], 10))
