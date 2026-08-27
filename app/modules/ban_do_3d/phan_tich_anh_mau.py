from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageStat

def analyze_reference(path: Path) -> dict:
    with Image.open(path) as im:
        rgb=im.convert("RGB")
        stat=ImageStat.Stat(rgb.resize((64,64)))
        mean=[round(x,1) for x in stat.mean]
        return {"width":im.width,"height":im.height,"aspect":round(im.width/max(1,im.height),4),"mean_rgb":mean}
