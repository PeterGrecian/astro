"""Normalise today's starcam frames to 1296x728. In-place."""
from pathlib import Path
from PIL import Image

TARGET = (1296, 728)
JPEG_QUALITY = 90
ROOT = Path.home() / "starcam-frames" / "day" / "2026-05-18"

total = {"skip":0,"wrote":0,"failed":0}
for hour_dir in sorted(ROOT.iterdir()):
    if not hour_dir.is_dir() or len(hour_dir.name) != 2: continue
    hs = {"skip":0,"wrote":0,"failed":0}
    for src in sorted(hour_dir.iterdir()):
        if not src.name.endswith(".jpg"): continue
        try:
            with Image.open(src) as im:
                if im.size == TARGET:
                    hs["skip"] += 1; continue
                img = im.convert("RGB")
            w,h = img.size
            if h*16 > w*9:
                crop_h = (w*9+15)//16
                if crop_h < h:
                    img = img.crop((0,0,w,crop_h))
            if img.size != TARGET:
                img = img.resize(TARGET, Image.Resampling.LANCZOS)
            img.save(src, "JPEG", quality=JPEG_QUALITY)
            hs["wrote"] += 1
        except Exception as e:
            hs["failed"] += 1
            print(f"  ERR {src}: {e}")
    print(f"  hour {hour_dir.name}: {hs}")
    for k in hs: total[k] += hs[k]
print(f"TOTAL: {total}")
