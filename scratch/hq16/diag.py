"""Why do epoch-2 frames give so few FWHM stars? Per frame: sky, noise, sources found,
and how many each map.py filter rejects. Args: frame paths."""
import sys, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from scipy.ndimage import gaussian_filter
for f in sys.argv[1:]:
    h = fits.open(f); d = h[1].data.astype(np.float32) - 256; hd = h[1].header
    b = d[0::2,0::2]+d[0::2,1::2]+d[1::2,0::2]+d[1::2,1::2]
    bk = Background2D(b,(64,64),filter_size=(3,3),bkg_estimator=MedianBackground()).background
    r = b - bk; _,_,sd = sigma_clipped_stats(r)
    seg = detect_sources(gaussian_filter(r,1), 5*sd, n_pixels=20)
    n = 0 if seg is None else seg.nlabels
    rej = dict(sat=0, round=0)
    smin=[]; smaj=[]
    if seg is not None:
        for s in SourceCatalog(r, seg):
            if s.max_value > 13000: rej["sat"]+=1; continue
            if s.semimajor_axis.value < 2*s.semiminor_axis.value: rej["round"]+=1
            smin.append(s.semiminor_axis.value); smaj.append(s.semimajor_axis.value)
    smin=np.array(smin); smaj=np.array(smaj)
    print(f, d.shape, "exp", hd.get("EXPTIME"), "pos", hd.get("POSINDEX"),
          "sky/binned %.0f sd %.1f" % (np.median(bk), sd), "sources", n, rej,
          "semimin med %.1f semimaj med %.1f" % (np.median(smin) if len(smin) else -1, np.median(smaj) if len(smaj) else -1))
