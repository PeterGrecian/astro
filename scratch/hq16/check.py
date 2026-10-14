import glob, os, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.io import fits
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from astropy.stats import sigma_clipped_stats
from scipy.ndimage import rotate, gaussian_filter
from scipy.optimize import curve_fit
from PIL import Image
f = sorted(glob.glob(os.environ["BIGSTORE"] + "/eclipticam-frames/night/2026-10-13/hq16/04/*.fits.fz"))[30]
d = fits.getdata(f, 1).astype(np.float32) - 256
b = d[0::2,0::2]+d[0::2,1::2]+d[1::2,0::2]+d[1::2,1::2]
r = b - Background2D(b,(64,64),filter_size=(3,3),bkg_estimator=MedianBackground()).background
_,_,sd = sigma_clipped_stats(r)
cat = SourceCatalog(r, detect_sources(gaussian_filter(r,1), 5*sd, n_pixels=20))
g = lambda x,a,m,s,c: a*np.exp(-.5*((x-m)/s)**2)+c
tiles=[]
for s in sorted(cat, key=lambda s: -s.segment_flux)[5:40]:
    x,y,th = int(s.x_centroid), int(s.y_centroid), s.orientation.value
    L, w = s.semimajor_axis.value, s.semiminor_axis.value
    cut = r[y-20:y+21, x-20:x+21]
    if cut.shape != (41,41): continue
    res=[]
    for sgn in (1,-1):
        rc = rotate(cut, sgn*th, reshape=False, order=1)
        p = rc[:, 20-int(L):20+int(L)+1].mean(1)
        try: q,_ = curve_fit(g, np.arange(41), p, p0=[p.max(),20,1.5,0]); res.append(2.355*abs(q[2]))
        except: res.append(np.nan)
    print(f"{x:5d} {y:5d} th={th:6.1f} L={2.355*L:5.1f} w_mom={2.355*w:4.2f}  +rot={res[0]:5.2f} -rot={res[1]:5.2f} peak={s.max_value:.0f}")
    tiles.append(cut)
t = np.vstack([np.hstack(tiles[i:i+6]) for i in range(0, 30, 6)])
t = np.clip(t/np.percentile(t,99.5),0,1)**0.5*255
Image.fromarray(t.astype(np.uint8)).resize((t.shape[1]*3,t.shape[0]*3),0).save(os.path.expanduser("~/tmp/hq16-tiles.png"))
print(f)
