"""Strip panels for a fan series: the plain fan.jpg of each stack (already cropped by render-fan) with one
large label, legible when the panel is shown ~330 px wide. Usage: strip.py <out dir> <stack dir>:<label>:<sub> ..."""
import sys, os
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
for spec in sys.argv[2:]:
    d, lab, sub = spec.split(":", 2); im = Image.open(f"{d}/fan.jpg").convert("RGB")
    k = im.width / 330                        # px of full image per displayed px
    dr = ImageDraw.Draw(im); f1 = ImageFont.truetype(F, int(24 * k)); f2 = ImageFont.truetype(F, int(15 * k))
    dr.text((int(10 * k), int(8 * k)), lab, fill=(224, 224, 224), font=f1)
    dr.text((int(10 * k), int(38 * k)), sub, fill=(142, 142, 147), font=f2)
    name = os.path.basename(d.rstrip("/")); im.save(f"{out}/strip-{name}.jpg", quality=90)
    im.resize((990, round(im.height * 990 / im.width)), Image.LANCZOS).save(f"{out}/strip-{name}-web.jpg", quality=85)
    print("wrote", f"{out}/strip-{name}.jpg")
