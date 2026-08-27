from __future__ import annotations

def normalize_placements(items: list[dict] | None) -> list[dict]:
    out=[]
    for i,item in enumerate(items or []):
        if not item.get("asset_id"): continue
        out.append({"asset_id":str(item["asset_id"]),"loai":str(item.get("loai","prop")),
                    "x":float(item.get("x",0)),"y":float(item.get("y",0)),"z":float(item.get("z",0)),
                    "rotation_y":float(item.get("rotation_y",0)),"scale":float(item.get("scale",1))})
    return out
