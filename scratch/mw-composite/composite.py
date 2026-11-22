#!/usr/bin/env python3
"""Our two Milky Way stacks as windows on the whole galaxy, in galactic coordinates (plate carree,
l increasing to the left, centred on l=100 so neither window is cut by the l=180 seam; the galactic
centre sits on the right). Two versions:
  A: windows on black with a galactic grid, the plane, and the centre marked
  B: windows on ESO's all-sky panorama (S. Brunier / ESO, CC BY 4.0, eso0932a: plate carree, galactic,
     centred on l=0; verified with the LMC 3x sky at its predicted pixel and sky level when mirrored)
North: astrocam 2026-10-07 derot stack (533 frames, aligned, 2x drizzle), night camera model, 23:06:09 UTC.
South: eclipticam-v3w 2026-11-12/13 derot stack (32 frames 03:40-04:20), night model, 04:00 UTC, privacy-cropped.
Each window: stack -> asinh stretch -> resampled into galactic pixels through the camera model (inverse:
galactic -> alt-az at the reference time -> ENU -> project). Writes ~/tmp/mwcomp/{A,B}.jpg."""
import json, numpy as np, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import sys; sys.path.insert(0, str(Path.home() / "astro"))
from astro.skyglow import CameraModel, _enu
from astropy.io import fits
from astropy.coordinates import SkyCoord, AltAz, EarthLocation, Galactic
from astropy.time import Time
import astropy.units as u
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None
OUT = Path.home() / "tmp/mwcomp"; LOC = EarthLocation(lat=51.3948 * u.deg, lon=-0.2923 * u.deg)
W, H = 6000, 3000; LC = 100.0                       # output grid = ESO's (0.06 deg/px), recentred on l=LC
DEG = W / 360
def lb_to_xy(l, b): return W / 2 - (((np.asarray(l) - LC + 180) % 360) - 180) * DEG, H / 2 - np.asarray(b) * DEG
def xy_to_lb(x, y): return (LC - (x - W / 2) / DEG) % 360, -(y - H / 2) / DEG
F = lambda n: ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{n}", 40)
FONT, SMALL = F("DejaVuSans.ttf"), ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)

def window(stack, cmfile, t, Z, keep_rows=None, gain=10.0, lo_p=20, hi_p=99.9, wfrac=0.6, yfix=0.0):
    data, wt = fits.getdata(stack, 0).astype(np.float32), fits.getdata(stack, 1).astype(np.float32)
    good = (wt > wfrac * np.nanmax(wt)) & np.isfinite(data)
    if keep_rows: good[keep_rows:] = False
    v = data[good]; lo, hi = np.percentile(v, lo_p), np.percentile(v, hi_p)
    img = np.arcsinh(gain * np.clip((np.nan_to_num(data, nan=lo) - lo) / (hi - lo), 0, None)) / np.arcsinh(gain)
    img = np.clip(img, 0, 1); img[~good] = np.nan
    cm = CameraModel(cmfile); T = Time(t); fr = AltAz(obstime=T, location=LOC, pressure=0)
    # coverage: unproject a coarse grid of good pixels -> l, b box
    ys, xs = np.nonzero(good[::24, ::24]); ys, xs = ys * 24, xs * 24
    e = cm.unproject(xs / Z, ys / Z); az, alt = np.degrees(np.arctan2(e[:, 0], e[:, 1])), np.degrees(np.arcsin(e[:, 2]))
    g = SkyCoord(az=az * u.deg, alt=alt * u.deg, frame=fr).transform_to(Galactic)
    X, Y = lb_to_xy(g.l.deg, g.b.deg)
    x0, x1, y0, y1 = int(X.min()) - 20, int(X.max()) + 20, int(Y.min()) - 20, int(Y.max()) + 20
    gy, gx = np.mgrid[y0:y1, x0:x1]; L, B = xy_to_lb(gx + 0.5, gy + 0.5)
    aa = SkyCoord(l=L.ravel() * u.deg, b=B.ravel() * u.deg, frame=Galactic).transform_to(fr)
    px, py = cm.project(_enu(np.radians(aa.az.deg), np.radians(aa.alt.deg)))
    px, py = np.asarray(px).reshape(L.shape) * Z, (np.asarray(py).reshape(L.shape) + yfix) * Z
    up = (aa.alt.deg.reshape(L.shape) > 0)
    val = ndi.map_coordinates(np.nan_to_num(img, nan=-1), [py, px], order=1, cval=-1)
    msk = ndi.map_coordinates(np.isfinite(img).astype(np.float32), [py, px], order=0, cval=0) > 0.5
    val[~(msk & up)] = np.nan
    print(f"{Path(stack).parent.name}: l {L[np.isfinite(val)].min():.0f}-{L[np.isfinite(val)].max():.0f}  b {B[np.isfinite(val)].min():.0f}..{B[np.isfinite(val)].max():.0f}  box {x1-x0}x{y1-y0}", flush=True)
    return (x0, y0), val

AC = Path("/mnt/muppet/bigstore/astrocam-frames/2026-10-07")
north = window(AC / "derot-sky-aligned-driz2.fits", AC / "skyglow-cammodel-night.json", "2026-10-07T23:06:09", 2, wfrac=0.2)   # the band is in only 200-300 of 533 frames
pj = json.load(open(Path.home() / "astro/eclipticam-v3w/privacy.json"))
keep = int(round(pj["publish_keep_top_px"] * 1296 / pj["frame_size_px"][1])) // 2 * 2
south = window(Path.home() / "tmp/mw-1112/stack/derot-sky.fits", Path.home() / "eclipticam-frames/night/2026-11-12/skyglow-cammodel.json",
               "2026-11-13T04:00:00", 1, keep_rows=keep, yfix=6.0)   # v3w stars sit +6 px below the model (STATE, colour bug a)

eso = np.asarray(Image.open(OUT / "dl/eso0932a.jpg").convert("RGB")).astype(np.float32) / 255
eso = np.roll(eso, int(round(LC * DEG)), axis=1)     # ESO is centred on l=0; ours on l=LC: x_ours = x_eso + LC*DEG
# check: LMC must land where lb_to_xy says
lx, ly = lb_to_xy(280.47, -32.89); print("LMC brightness at predicted px (should be >> sky):", round(float(ndi.uniform_filter(eso.mean(2), 41)[int(ly), int(lx)] * 255), 1), "sky", round(float(np.median(eso) * 255), 1))

# alignment check: named bright stars at catalogue positions; offset of the brightest pixel within 1 deg
from astropy.coordinates import ICRS
STARS = {"north": [("Polaris", 37.955, 89.264), ("Kochab", 222.676, 74.156), ("Schedar", 10.127, 56.537), ("Caph", 2.295, 59.150),
                   ("Mirfak", 51.081, 49.861), ("Algol", 47.042, 40.956), ("Errai", 354.837, 77.632), ("Ruchbah", 21.454, 60.235)],
         "south": [("Rigel", 78.634, -8.202), ("Betelgeuse", 88.793, 7.407), ("Sirius", 101.287, -16.716), ("Procyon", 114.825, 5.225),
                   ("Bellatrix", 81.283, 6.350), ("Alnilam", 84.053, -1.202), ("Saiph", 86.939, -9.670), ("Aldebaran", 68.980, 16.509)]}
lumE = ndi.gaussian_filter(eso.mean(2), 1.5)
for name, ((x0, y0), val) in (("north", north), ("south", south)):
    f = ndi.gaussian_filter(np.nan_to_num(val, nan=0), 1.5); out = []
    for st, ra, dec in STARS[name]:
        g = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS).galactic; X, Y = lb_to_xy(g.l.deg, g.b.deg)
        for tag, im, ox, oy in (("ours", f, x0, y0), ("eso", lumE, 0, 0)):
            x, y = int(round(float(X))) - ox, int(round(float(Y))) - oy; R = int(DEG)
            sub = im[max(y - R, 0):y + R + 1, max(x - R, 0):x + R + 1]
            if sub.size < (2 * R + 1) ** 2 or (tag == "ours" and not np.isfinite(val[y, x])): out.append((st, tag, None)); continue
            yy, xx = np.unravel_index(np.argmax(sub), sub.shape); out.append((st, tag, (round((xx - R) * 0.06, 2), round((yy - R) * 0.06, 2))))
    print(f"stars {name} (offset of peak from catalogue, deg dx,dy; None = outside):"); [print("   ", o) for o in out]

def paint(base, dim_base):
    im = base.copy()
    if dim_base: im *= 0.55
    outl = []
    for (x0, y0), val in (north, south):
        ok = np.isfinite(val); h, w = val.shape; reg = im[y0:y0 + h, x0:x0 + w]
        v = np.clip(val, 0, 1)[..., None] * np.array([0.92, 0.96, 1.0])     # our mono stacks, faintly cool
        reg[ok] = v[ok]
        edge = ok & ~ndi.binary_erosion(ok, iterations=3); outl.append((x0, y0, edge))
    for x0, y0, edge in outl:
        ys, xs = np.nonzero(edge); im[ys + y0, xs + x0] = (1.0, 0.584, 0.0)
    return Image.fromarray((np.clip(im, 0, 1) * 255).astype(np.uint8))

def annotate(img, grid):
    d = ImageDraw.Draw(img, "RGBA")
    if grid:
        for l in range(0, 360, 30):
            x, _ = lb_to_xy(l, 0); d.line([x, 0, x, H], fill=(44, 44, 46, 255), width=2); d.text((x + 8, H / 2 + 12), f"l {l}", fill=(142, 142, 147), font=SMALL)
        for b in (-60, -30, 30, 60):
            _, y = lb_to_xy(0, b); d.line([0, y, W, y], fill=(44, 44, 46, 255), width=2); d.text((10, y + 6), f"b {b:+d}", fill=(142, 142, 147), font=SMALL)
        _, y = lb_to_xy(0, 0); d.line([0, y, W, y], fill=(0, 122, 255, 160), width=3)
        d.text((20, y - 50), "galactic plane", fill=(0, 122, 255), font=SMALL)
    gx, gy = lb_to_xy(0, 0); r = 60
    d.ellipse([gx - r, gy - r, gx + r, gy + r], outline=(255, 59, 48), width=5)
    d.line([gx - 2 * r, gy, gx - r, gy], fill=(255, 59, 48), width=5); d.line([gx + r, gy, gx + 2 * r, gy], fill=(255, 59, 48), width=5)
    d.text((gx - 330, gy + 80), "galactic centre (Sagittarius A*)", fill=(255, 59, 48), font=FONT)
    d.text((gx - 330, gy + 130), "26,000 light years away; from Surbiton", fill=(224, 224, 224), font=SMALL)
    d.text((gx - 330, gy + 168), "it never rises more than ~10 deg (Dec -29)", fill=(224, 224, 224), font=SMALL)
    ax, ay = lb_to_xy(180, 0); d.text((ax - 160, ay + 60), "anticentre (l 180)", fill=(142, 142, 147), font=SMALL)
    for lab, sub, (l, b) in (("astrocam, looking north", "Cassiopeia - Perseus, 7-8 Oct, 533 x 60 s", (130, 24)),
                             ("eclipticam-v3w, looking south", "Orion - Monoceros, 13 Nov, 32 x 60 s", (206, -36))):
        x, y = lb_to_xy(l, b); d.text((x - 260, y), lab, fill=(255, 149, 0), font=FONT); d.text((x - 260, y + 48), sub, fill=(224, 224, 224), font=SMALL)
    # scale: 10 deg along the plane (plate carree is true scale along b=0 only)
    x, y = 120, H - 120; d.line([x, y, x + 10 * DEG, y], fill=(255, 255, 255), width=6); d.text((x, y - 50), "10 deg (true along the plane)", fill=(255, 255, 255), font=SMALL)
    d.text((W - 1900, H - 60), "Galactic coordinates, plate carree, l increasing to the left, centred on l 100", fill=(142, 142, 147), font=SMALL)
    return img

A = annotate(paint(np.zeros((H, W, 3), np.float32), False), True)
A.save(OUT / "A.jpg", quality=90)
B = annotate(paint(eso, True), False)
ImageDraw.Draw(B).text((W - 1900, H - 105), "Background: ESO/S. Brunier, Milky Way panorama (CC BY 4.0). Windows: our stacks", fill=(224, 224, 224), font=SMALL)
B.save(OUT / "B.jpg", quality=90)
B.crop((0, 600, W, 2400)).save(OUT / "B-band.jpg", quality=90)
print("wrote", OUT)
