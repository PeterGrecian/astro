"""Quick look: G channel of an HQ16 frame, 2x2 binned, sky-stretched, a 600x600 centre crop
beside the full frame at 1/4, written as JPEG; plus moon altitude/illumination at DATE-OBS.
Args: out.jpg frame..."""
import sys, numpy as np
from astropy.io import fits
from PIL import Image
from astropy.time import Time
from astropy.coordinates import get_body, AltAz, EarthLocation, get_sun
import astropy.units as u
loc = EarthLocation(lat=51.39*u.deg, lon=-0.29*u.deg)
out = sys.argv[1]; tiles = []
for f in sys.argv[2:]:
    h = fits.open(f); d = h[1].data.astype(np.float32) - 256
    g = d[0::2,1::2] + d[1::2,0::2]
    lo, hi = np.percentile(g, [5, 99.7])
    im = np.clip((g-lo)/(hi-lo), 0, 1) ** 0.5 * 255
    H, W = im.shape
    crop = im[H//2-300:H//2+300, W//2-300:W//2+300]
    small = im[::4, ::4][:600, :507]
    tiles.append(np.hstack([crop, np.pad(small, ((0, 600-small.shape[0]), (0, 507-small.shape[1])))]))
    t = Time(h[1].header["DATE-OBS"].replace("+00:00", ""))
    aa = AltAz(obstime=t, location=loc)
    m = get_body("moon", t, loc); s = get_sun(t)
    elong = s.separation(m).deg
    print(f, t.iso, "moon alt %.1f az %.1f illum %.0f%%" % (m.transform_to(aa).alt.deg, m.transform_to(aa).az.deg, 50*(1-np.cos(np.radians(elong)))))
Image.fromarray(np.vstack(tiles).astype(np.uint8)).save(out, quality=85)
