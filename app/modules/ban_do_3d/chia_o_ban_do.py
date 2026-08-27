from __future__ import annotations
import math

def grid_for_count(count: int, aspect: float = 16/9) -> tuple[int,int]:
    best = None
    for rows in range(1, count + 1):
        cols = math.ceil(count / rows)
        ratio = cols / rows
        score = abs(ratio - aspect) + (rows*cols-count)*0.12
        if best is None or score < best[0]: best = (score, rows, cols)
    return best[1], best[2]

def build_tiles(count: int, tile_size: int, overlap: int):
    rows, cols = grid_for_count(count)
    tiles=[]
    idx=0
    for r in range(rows):
        for c in range(cols):
            if idx >= count: break
            tid=f"tile_{r:02d}_{c:02d}"
            neigh={"left":f"tile_{r:02d}_{c-1:02d}" if c>0 else None,
                   "right":f"tile_{r:02d}_{c+1:02d}" if c+1<cols and idx+1<count else None,
                   "top":f"tile_{r-1:02d}_{c:02d}" if r>0 else None,
                   "bottom":f"tile_{r+1:02d}_{c:02d}" if r+1<rows and (r+1)*cols+c<count else None}
            tiles.append({"tile_id":tid,"index":idx,"row":r,"col":c,"neighbors":neigh,
                          "world_bbox":{"x":c,"z":r,"w":1,"h":1},"overlap_px":overlap,"tile_size":tile_size})
            idx+=1
    return {"rows":rows,"cols":cols,"tiles":tiles}
