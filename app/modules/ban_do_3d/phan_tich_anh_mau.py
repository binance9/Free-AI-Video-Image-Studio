from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageStat

def analyze_reference(path: Path) -> dict:
    with Image.open(path) as im:
        rgb=im.convert("RGB")
        stat=ImageStat.Stat(rgb.resize((64,64)))
        mean=[round(x,1) for x in stat.mean]
        edge_hint=ImageStat.Stat(rgb.resize((128,128)).convert("L")).mean[0]/255
        return {"width":im.width,"height":im.height,"aspect":round(im.width/max(1,im.height),4),"mean_rgb":mean,"forest_density":"unknown-reference-only","settlement_zone":"analyze-as-zone-only","prop_density":"reference-context-only","texture_activity":round(edge_hint,4)}
