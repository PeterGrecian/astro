"""Find heavily defocused stars on HQ16 frames: sum N consecutive frames' G (2x2 binned),
smooth at sigma=SM binned px, detect at 4 sigma, report size of the larger blobs
(semi-minor/major, equivalent radius, FWHM by moments) and their positions.
Args: SM N frame... (frames consecutive; summed directly, so trails grow by ~6 px/frame)."""
import sys, numpy as np, warnings
warnings.filterwarnings("ignore")
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog
from scipy.ndimage import gaussian_filter
sm = float(sys.argv[1]); fs = sys.argv[2:]
acc = None
for f in fs:
    d = fits.getdata(f, 1).astype(np.float32) - 256
    g = d[0::2,1::2] + d[1::2,0::2]
    acc = g if acc is None else acc + g
r = acc - Background2D(acc,(128,128),filter_size=(3,3),bkg_estimator=MedianBackground()).background
_,_,sd = sigma_clipped_stats(r)
rs = gaussian_filter(r, sm); _,_,sds = sigma_clipped_stats(rs)
seg = detect_sources(rs, 4*sds, n_pixels=int(3*sm*sm))
print(fs[0], "frames", len(fs), "sd", round(float(sd),1), "n", 0 if seg is None else seg.nlabels)
if seg is None: sys.exit()
cat = sorted(SourceCatalog(r, seg), key=lambda s: -s.segment_flux)[:15]
for s in cat:
    print("  x %5.0f y %5.0f flux %8.0f peak %6.0f semimin %5.1f semimaj %5.1f fwhm %5.1f" % (
        s.x_centroid, s.y_centroid, s.segment_flux, s.max_value, s.semiminor_axis.value, s.semimajor_axis.value, s.fwhm.value))
