from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

from app.core.prompt_contract import build_priority_prompt

def crop_reference_tile(reference: Path, tile: dict, grid: dict, out: Path, size: int, overlap_px: int):
    with Image.open(reference) as im:
        im=im.convert("RGB")
        rows, cols = grid["rows"], grid["cols"]
        cell_w=im.width/cols; cell_h=im.height/rows
        r,c=tile["row"],tile["col"]
        ox=overlap_px/size*cell_w; oy=overlap_px/size*cell_h
        box=(max(0,c*cell_w-ox), max(0,r*cell_h-oy), min(im.width,(c+1)*cell_w+ox), min(im.height,(r+1)*cell_h+oy))
        part=im.crop(tuple(map(int,box))).resize((size,size), Image.Resampling.LANCZOS)
        # Reference chỉ truyền macro layout/màu/địa hình. Làm mờ chi tiết nhỏ để
        # img2img không copy chữ, UI, cây, nhà và prop từ ảnh mẫu vào terrain.
        # Only pass macro colour/layout into img2img. Strong downsampling removes
        # text, UI and asset silhouettes more reliably than blur alone.
        guide_side=max(24,min(48,size//24))
        part=part.resize((guide_side,guide_side),Image.Resampling.BOX)
        part=part.resize((size,size),Image.Resampling.BICUBIC)
        part=part.filter(ImageFilter.GaussianBlur(radius=2))
        part=ImageEnhance.Contrast(part).enhance(.88)
        part.save(out, quality=96)

def tile_prompt(spec: dict, tile: dict, ref_context: dict | None) -> str:
    # Geometry, seed, neighbor và overlap đi bằng reference/data; không nhét vào CLIP prompt.
    # Nhưng ý nghĩa map gốc PHẢI đi theo từng tile (biome/đường/sông/phong cách)
    # để bước img2img không biến tile thành một terrain chung chung khác yêu cầu.
    return build_priority_prompt(
        spec.get("prompt") or f"{tile.get('biome','mixed')} terrain",
        mandatory=[f"tile biome: {tile.get('biome','mixed')}; preserve the locked master terrain layout and broad reference colors"],
        composition=[
            "sharp top-down terrain; ground and water only",
            "No trees, houses or props; No text, labels, icons, UI, borders or frames",
        ],
        quality=[spec.get("style") or "coherent fantasy game map"],
        max_words=58,
        core_max_words=24,
        core_label="MAP TILE REQUIREMENT",
    )
