"""Noise of a stack from two independent halves: sigma(A - B)/2 after high-pass, over common coverage = noise of (A+B)/2.
Usage: halfdiff.py <A dir> <B dir> [...pairs]"""
import sys, numpy as np, warnings; warnings.filterwarnings("ignore")
from astropy.io import fits
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from stack import lowpass
a = sys.argv[1:]
for A, B in zip(a[::2], a[1::2]):
    ma, wa = fits.getdata(A + "/derot-sky.fits", 0), np.nan_to_num(fits.getdata(A + "/derot-sky.fits", 1))
    mb, wb = fits.getdata(B + "/derot-sky.fits", 0), np.nan_to_num(fits.getdata(B + "/derot-sky.fits", 1))
    ok = (wa > 0.3 * wa.max()) & (wb > 0.3 * wb.max()) & np.isfinite(ma) & np.isfinite(mb)
    d = np.nan_to_num(ma - mb); d = d - lowpass(d, ok); v = d[ok]
    print(f"{A} vs {B}: common {ok.sum()} px, noise of the mean {1.4826 * np.median(np.abs(v - np.median(v))) / 2:.3f} ADU")
