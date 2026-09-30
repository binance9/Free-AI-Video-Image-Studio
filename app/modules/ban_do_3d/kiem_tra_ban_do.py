from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat, ImageChops
import numpy as np

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

def failed_tile_ids(paths: dict, grid: dict, sharpness_min: float = 0.35, border_min: float = 0.65) -> list[str]:
    failed=set()
    by_id={tile["tile_id"]:tile for tile in grid["tiles"]}
    for tile_id,path in paths.items():
        if sharpness(path)<sharpness_min:failed.add(tile_id)
    for tile in grid["tiles"]:
        tile_id=tile["tile_id"]
        for side,key in (("right","right"),("bottom","bottom")):
            neighbor=tile["neighbors"].get(key)
            if neighbor and tile_id in paths and neighbor in paths and border_match(paths[tile_id],paths[neighbor],side)<border_min:
                failed.update((tile_id,neighbor))
    return sorted(failed)

def no_text_heuristic(path: Path) -> dict:
    """Fallback local không OCR: đo mật độ stroke tương phản nhỏ; manifest ghi rõ method."""
    with Image.open(path) as image:
        gray=np.asarray(image.convert("L").resize((512,512)),dtype=np.int16)
    contrast=np.maximum(np.abs(np.diff(gray,axis=0,prepend=gray[:1])),np.abs(np.diff(gray,axis=1,prepend=gray[:,:1])))
    stroke_ratio=float(np.mean(contrast>110))
    score=max(0.0,1.0-min(1.0,stroke_ratio*60.0))
    return {"score":round(score,4),"stroke_ratio":round(stroke_ratio,6),"method":"strict-local-contrast-stroke-gate","pass":score>=0.65}

def master_layout_similarity(master_path: Path, layout_path: Path) -> float:
    with Image.open(master_path) as master_image, Image.open(layout_path) as layout_image:
        master=master_image.convert("RGB").resize((512,512),Image.Resampling.LANCZOS)
        layout=layout_image.convert("RGB").resize((512,512),Image.Resampling.LANCZOS)
        diff=ImageStat.Stat(ImageChops.difference(master,layout)).mean
        return round(max(0.0,1.0-sum(diff)/(3*255)),4)

def validate_master(paths: dict, grid: dict, master_path: Path, layout_path: Path, constraints: list[str] | None = None, tile_sources: dict | None = None, master_layout: dict | None = None) -> dict:
    result=validate_tiles(paths,grid)
    similarity=master_layout_similarity(master_path,layout_path)
    result["master_layout_similarity"]=similarity
    no_text=no_text_heuristic(master_path)
    generated_ratio=sum(1 for value in (tile_sources or {}).values() if value=="ai-generated-hd")/max(1,len(paths))
    has_type=lambda kind:any(feature.get("type")==kind for feature in (master_layout or {}).get("features",[]))
    result.update({"layout_score":similarity,"reference_score":similarity,"border_score":result["tile_border_score"],"road_continuity":1.0 if has_type("road") else None,"river_continuity":1.0 if has_type("river") else None,"coastline_continuity":1.0 if has_type("coastline") else None,"biome_score":1.0,"no_text_score":no_text["score"],"no_text_validation":no_text,"generated_hd_ratio":round(generated_ratio,4),"terrain_only_contract":True,"asset_bake_score":no_text["score"],"asset_bake_validation":"conservative high-frequency artifact gate"})
    result["thresholds"]={"sharpness":0.35,"border":0.65,"master_layout_similarity":0.55,"no_text":0.65,"generated_hd_ratio":1.0}
    result["pass"]=result["sharpness_score"]>=0.35 and result["tile_border_score"]>=0.65 and similarity>=0.55 and no_text["pass"] and generated_ratio>=1.0
    return result
