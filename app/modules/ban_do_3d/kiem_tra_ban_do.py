from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat, ImageChops

def sharpness(path: Path) -> float:
    with Image.open(path) as im:
        g=im.convert("L").resize((512,512))
        edges=g.filter(ImageFilter.FIND_EDGES)
        return min(1.0, (ImageStat.Stat(edges).mean[0] / 24.0))

def border_match(a: Path,b: Path,side: str,band: int=24) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        ia=ia.convert("RGB").resize((512,512)); ib=ib.convert("RGB").resize((512,512))
        if side=="right": ca=ia.crop((512-band,0,512,512)); cb=ib.crop((0,0,band,512))
        else: ca=ia.crop((0,512-band,512,512)); cb=ib.crop((0,0,512,band))
        diff=ImageStat.Stat(ImageChops.difference(ca,cb)).mean
        return max(0.0,1.0-sum(diff)/(3*255))

def validate_tiles(paths: dict, grid: dict) -> dict:
    s=[]; borders=[]
    for t in grid["tiles"]:
        p=paths.get(t["tile_id"])
        if p and p.exists(): s.append(sharpness(p))
        rn=t["neighbors"].get("right"); bn=t["neighbors"].get("bottom")
        if rn and p and rn in paths: borders.append(border_match(p,paths[rn],"right"))
        if bn and p and bn in paths: borders.append(border_match(p,paths[bn],"bottom"))
    sharp=sum(s)/len(s) if s else 0
    border=sum(borders)/len(borders) if borders else 1
    overall=0.55*sharp+0.45*border
    return {"sharpness_score":round(sharp,4),"tile_border_score":round(border,4),"overall_score":round(overall,4),"pass":overall>=0.42}
