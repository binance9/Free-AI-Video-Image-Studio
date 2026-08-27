from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

def crop_reference_tile(reference: Path, tile: dict, grid: dict, out: Path, size: int, overlap_px: int):
    with Image.open(reference) as im:
        im=im.convert("RGB")
        rows, cols = grid["rows"], grid["cols"]
        cell_w=im.width/cols; cell_h=im.height/rows
        r,c=tile["row"],tile["col"]
        ox=overlap_px/size*cell_w; oy=overlap_px/size*cell_h
        box=(max(0,c*cell_w-ox), max(0,r*cell_h-oy), min(im.width,(c+1)*cell_w+ox), min(im.height,(r+1)*cell_h+oy))
        part=im.crop(tuple(map(int,box))).resize((size,size), Image.Resampling.LANCZOS)
        part=ImageEnhance.Sharpness(part).enhance(1.12)
        part=ImageEnhance.Contrast(part).enhance(1.04)
        part.save(out, quality=96)

def tile_prompt(spec: dict, tile: dict, ref_context: dict | None) -> str:
    n=tile["neighbors"]
    return (
        "Create ONE high-resolution tile of a larger seamless game world map. "
        f"Master request: {spec.get('prompt') or 'follow the reference map exactly'}. "
        f"Style: {spec['style']}; view: {spec['view']}. "
        f"This is tile row {tile['row']} column {tile['col']}. "
        "Preserve roads, rivers, coastlines, terrain elevation cues, biome borders and architecture across all tile edges. "
        "Do not add labels, text, borders, UI, legends or frames. Do not change the overall layout. "
        "Keep the entire tile uniformly sharp with fine ground detail suitable for close zoom. "
        f"Neighbor continuity: left={n['left']}, right={n['right']}, top={n['top']}, bottom={n['bottom']}."
    )
