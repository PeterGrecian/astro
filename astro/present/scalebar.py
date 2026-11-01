"""Scale bar for a rendered image (house rule: every image where size matters carries one)."""
from PIL import Image, ImageDraw, ImageFont

_NICE_ARCMIN = (120, 60, 30, 15, 10, 5, 2, 1)


def stamp(path, deg_across, quality=92):
    """Draw a labelled bar, bottom left, on the image at path, whose width spans deg_across."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    per_px = deg_across * 60 / w
    arcmin = next((a for a in _NICE_ARCMIN if a / per_px <= w / 4), _NICE_ARCMIN[-1])
    bar = int(round(arcmin / per_px))
    label = f"{arcmin // 60} deg" if arcmin >= 60 else f"{arcmin} arcmin"
    d = ImageDraw.Draw(im)
    size = max(12, w // 60)
    font = ImageFont.load_default(size)
    x, y = w // 50, h - h // 40
    d.rectangle((x - 6, y - size - 16, x + bar + 6, y + 10), fill=(0, 0, 0))
    d.rectangle((x, y, x + bar, y + 4), fill=(224, 224, 224))
    d.text((x, y - size - 10), label, fill=(224, 224, 224), font=font)
    im.save(path, quality=quality)
