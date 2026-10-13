"""Figures for the field note 2026-10-13-milky-way (astrocam, night 2026-10-07).

Both images share one geometry: the 23:05:39 UTC frame (00:05 BST 8 Oct), which
is also the derot stack's reference time, so one projection labels both. Uses
the NIGHT's refined camera model (astrocam moved 1.04 deg after 09-22; the
first overlay used the old model and its circles missed by ~30 px).
"""
import sys, warnings, numpy as np
sys.path.insert(0, "/home/peter/astro"); warnings.filterwarnings("ignore")
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
from astropy.time import Time
import astropy.units as u
from astro.skyglow import CameraModel, _enu

D = Path("/mnt/muppet/bigstore/astrocam-frames/2026-10-07")
OUT = Path("/home/peter/astro/notes/figs/2026-10-13-milky-way"); OUT.mkdir(parents=True, exist_ok=True)
cm = CameraModel(str(D / "skyglow-cammodel-night.json"))
T = Time("2026-10-07T23:06:09")
loc = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)

def pix(c):
    aa = c.transform_to(AltAz(obstime=T, location=loc, pressure=0))
    x, y = cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    return np.atleast_1d(x) * Z, np.atleast_1d(y) * Z

Z = 2   # the drizzled stack is on a 2x grid (photosites); the camera model is on the binned grid
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34 * Z)
SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26 * Z)
AMBER, BLUE = (255, 149, 0), (0, 122, 255)

# (label, ra, dec, dx, dy) label offset from the star, binned pixels
STARS = [("Polaris", 37.955, 89.264, 26, -14), ("Kochab", 222.676, 74.156, 26, -14),
         ("Errai", 354.837, 77.632, 26, -14), ("Mirfak", 51.081, 49.861, -150, -50),
         ("Algol", 47.042, 40.956, -110, -50)]
GROUPS = [("Cassiopeia", [(2.295, 59.150), (10.127, 56.537), (14.177, 60.717), (21.454, 60.235), (28.599, 63.670)], -300, 40),
          ("Double Cluster", [(34.75, 57.13)], 34, -10), ("Alpha Per cluster", [(51.68, 49.0)], 40, 30)]

def label(img):
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    for b, w, a in [(0, 5, 200), (10, 2, 120), (-10, 2, 120)]:          # galactic plane and +/-10 deg
        l = np.arange(60, 220, 0.5)
        x, y = pix(SkyCoord(l=l * u.deg, b=np.full_like(l, b) * u.deg, frame=Galactic))
        pts = [(float(a_), float(b_)) for a_, b_ in zip(x, y) if -50 < a_ < W + 50 and -50 < b_ < H + 50]
        d.line(pts, fill=BLUE + (a,), width=w * Z)
    for name, ra, dec, dx, dy in STARS:
        x, y = pix(SkyCoord(ra * u.deg, dec * u.deg)); x, y = float(x[0]), float(y[0])
        d.ellipse([x - 16 * Z, y - 16 * Z, x + 16 * Z, y + 16 * Z], outline=AMBER, width=3 * Z)
        d.text((x + dx * Z, y + dy * Z), name, font=FONT, fill=AMBER)
    for name, pts, dx, dy in GROUPS:
        x, y = pix(SkyCoord([p[0] for p in pts] * u.deg, [p[1] for p in pts] * u.deg))
        if len(pts) > 1:
            for a_, b_ in zip(x, y): d.ellipse([a_ - 12 * Z, b_ - 12 * Z, a_ + 12 * Z, b_ + 12 * Z], outline=AMBER, width=3 * Z)
            d.text((float(x.mean()) + dx * Z, float(y.mean()) + dy * Z), name, font=FONT, fill=AMBER)
        else:
            r = 34 * Z; d.ellipse([x[0] - r, y[0] - r, x[0] + r, y[0] + r], outline=AMBER, width=3 * Z)
            d.text((float(x[0]) + r + (dx - 30) * Z, float(y[0]) + dy * Z), name, font=FONT, fill=AMBER)
    d.text((24 * Z, H - 46 * Z), "blue: the plane of the Milky Way (galactic equator), thin lines 10° either side",
           font=SMALL, fill=(224, 224, 224))
    return img

stack = Image.open(D / "derot-sky-aligned-driz2.jpg").convert("RGB")   # 4608 x 2592
binned = Image.open(D / "derot-sky.jpg").convert("RGB")
single = Image.open(D / "milkyway-0005.jpg").convert("RGB")
stack.save(OUT / "stack.jpg", quality=90)
label(stack.copy()).save(OUT / "stack-labelled.jpg", quality=90)

# side by side: one frame vs the night, on the Cassiopeia-Perseus stretch of the band
box = (1300, 0, 2100, 900)
a, b = single.crop(box), binned.crop(box)   # both on the binned grid: same scale
pair = Image.new("RGB", (a.width * 2 + 16, a.height), (0, 0, 0))
pair.paste(a, (0, 0)); pair.paste(b, (a.width + 16, 0))
d = ImageDraw.Draw(pair)
d = ImageDraw.Draw(pair); FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
d.text((20, 16), "one 60 s frame, 00:05 BST", font=FONT, fill=(224, 224, 224))
d.text((a.width + 36, 16), "the whole night, de-rotated", font=FONT, fill=(224, 224, 224))
pair.save(OUT / "frame-vs-night.jpg", quality=90)
Image.open(D / "skyglow.png").save(OUT / "skyglow.png")

# fields, for the frontmatter
def span(x0, y0, x1, y1):
    v = cm.unproject(np.array([x0, x1, (x0 + x1) / 2, (x0 + x1) / 2]), np.array([(y0 + y1) / 2] * 2 + [y0, y1]))
    ang = lambda p, q: np.degrees(np.arccos(np.clip(v[p] @ v[q], -1, 1)))
    return ang(0, 1), ang(2, 3)
print("whole frame %.0f x %.0f deg" % span(0, 0, 2303, 1295))
print("crop %.0f x %.0f deg" % span(*box))

# the band at 1:1 on the drizzled grid: add-note caps figures at 2560 wide, so
# the whole 4608-wide frame is shrunk on the site; this crop is not
bbox = (1250, 0, 2250, 1296)                      # binned grid
stack.crop(tuple(v * Z for v in bbox)).save(OUT / "band-full-res.jpg", quality=92)
print("band crop %.0f x %.0f deg" % span(*bbox))

# ---- second night, 10-09, 15 s frames: drizzled stack built 10-13 on muppet
#      (~/tmp/derot1009, ref 22:57:47 UTC = the same sky orientation as 10-07 23:05:39)
from pathlib import Path as _P
S09 = Image.open(_P.home() / "tmp/derot1009/derot-sky.jpg").convert("RGB")
S09.save(OUT / "stack-1009.jpg", quality=90)
cm09 = CameraModel(str(D.parent / "2026-10-09/skyglow-cammodel.json"))
def dpix(cmx, T_, ra, dec):
    aa = SkyCoord(ra * u.deg, dec * u.deg).transform_to(AltAz(obstime=T_, location=loc, pressure=0))
    x, y = cmx.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    return 2 * float(x) + 0.5, 2 * float(y) + 0.5
# the band, 1:1, centred between Cassiopeia and the Double Cluster, both nights
RA0, DEC0 = 20.0, 60.0
cw, ch = 1200, 2000
crops = []
for img, cmx, T_ in ((stack, cm, Time("2026-10-07T23:05:39")), (S09, cm09, Time("2026-10-09T22:57:47"))):
    X, Y = dpix(cmx, T_, RA0, DEC0)
    x0, y0 = int(X - cw / 2), max(0, int(Y - ch / 2))
    crops.append(img.crop((x0, y0, x0 + cw, y0 + ch)))
pair2 = Image.new("RGB", (2 * cw + 16, ch), (0, 0, 0))
pair2.paste(crops[0], (0, 0)); pair2.paste(crops[1], (cw + 16, 0))
d = ImageDraw.Draw(pair2)
d.text((24, 20), "7-8 Oct, 60 s frames", font=FONT, fill=(224, 224, 224))
d.text((cw + 40, 20), "9-10 Oct, 15 s frames", font=FONT, fill=(224, 224, 224))
pair2.save(OUT / "band-two-nights.jpg", quality=92)
X, Y = dpix(cm, Time("2026-10-07T23:05:39"), RA0, DEC0)
bx = ((X - cw / 2 - 0.5) / 2, max(0, (Y - ch / 2 - 0.5) / 2))
print("two-night crop %.0f x %.0f deg" % span(bx[0], bx[1], bx[0] + cw / 2, bx[1] + ch / 2))
