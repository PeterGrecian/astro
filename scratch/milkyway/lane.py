"""10-09 deep-sweep frames with the galactic plane drawn at each frame's own time."""
import sys, warnings, numpy as np
sys.path.insert(0, "/home/peter/astro"); warnings.filterwarnings("ignore")
from PIL import Image, ImageDraw, ImageFont
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
from astropy.time import Time
import astropy.units as u
from astro.skyglow import CameraModel, _enu
cm = CameraModel("/mnt/muppet/bigstore/astrocam-frames/2026-10-09/skyglow-cammodel.json")
loc = EarthLocation(lat=51.3948*u.deg, lon=-0.2923*u.deg)
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
tiles = []
for n in (0, 60, 120, 180, 240, 300):
    T = Time("2026-10-09T22:00:00") + n * u.min
    im = Image.open("/tmp/claude-1000/-home-peter-strands-astro-science/fcd47f37-b686-4569-94bb-ca297a5ad360/scratchpad/lane/f%d.png" % n).convert("RGB"); d = ImageDraw.Draw(im, "RGBA")
    for b, w in ((0, 5), (10, 2), (-10, 2)):
        l = np.arange(0, 360, 0.5); g = SkyCoord(l=l*u.deg, b=np.full_like(l, b)*u.deg, frame=Galactic)
        aa = g.transform_to(AltAz(obstime=T, location=loc, pressure=0))
        x, y = cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
        ok = (x > -100) & (x < 2400) & (y > -100) & (y < 1400) & (aa.alt.deg > -5)
        seg = []
        for xi, yi, k in zip(x, y, ok):
            if k: seg.append((float(xi), float(yi)))
            elif len(seg) > 1: d.line(seg, fill=(0, 122, 255, 200), width=w); seg = []
            else: seg = []
        if len(seg) > 1: d.line(seg, fill=(0, 122, 255, 200), width=w)
    d.text((30, 30), "~%s UTC" % (T + 0*u.s).datetime.strftime("%H:%M"), font=F, fill=(255, 149, 0))
    im.thumbnail((800, 450)); tiles.append(im)
out = Image.new("RGB", (1600, 1350))
for i, t in enumerate(tiles): out.paste(t, ((i % 2) * 800, (i // 2) * 450))
out.save("/tmp/claude-1000/-home-peter-strands-astro-science/fcd47f37-b686-4569-94bb-ca297a5ad360/scratchpad/lane/lane-grid.jpg", quality=88)
