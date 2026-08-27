from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def stitch(tile_paths: dict[str, Path], grid: dict, tile_size: int, out: Path, overlap_px: int = 0) -> dict:
    """Ghep tile thanh 1 anh map day du, dat tile CHONG LEN NHAU that su
    (stride = tile_size - overlap_px, khong phai dat canh-doi-canh) roi
    feather-blend (gradient tuyen tinh) trong vung chong lan. Tat ca tile
    deu duoc crop tu CUNG MOT bo_cuc_tong (xem khoa_bo_cuc.py) nen noi dung
    trong vung overlap giua 2 tile ke nhau la RAT GIONG NHAU - blend o day
    chu yeu de xoa vet AI tinh chinh rieng tung tile, khong lam meo hinh.

    Neu dat tile canh-doi-canh (khong chong) nhu ban cu, se KHONG CO vung
    pixel chung nao de blend that (chi blend voi nen chua ve) - day la ly
    do bat buoc phai doi sang layout co overlap that trong canvas."""
    cols, rows = grid["cols"], grid["rows"]
    ov = max(0, min(int(overlap_px), tile_size // 2))
    step = tile_size - ov
    width = cols * step + ov
    height = rows * step + ov
    canvas = np.full((height, width, 3), (20, 24, 30), dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, ov, dtype=np.float32) if ov > 1 else None

    for t in sorted(grid["tiles"], key=lambda x: (x["row"], x["col"])):
        p = tile_paths.get(t["tile_id"])
        if not (p and p.exists()):
            continue
        with Image.open(p) as im:
            arr = np.asarray(im.convert("RGB").resize((tile_size, tile_size), Image.Resampling.LANCZOS), dtype=np.float32)
        x0, y0 = t["col"] * step, t["row"] * step
        blended = arr

        if ramp is not None and t["neighbors"].get("left") is not None:
            existing = canvas[y0:y0 + tile_size, x0:x0 + ov, :]
            a = ramp.reshape(1, -1, 1)
            blended = blended.copy()
            blended[:, :ov, :] = existing * (1 - a) + blended[:, :ov, :] * a

        if ramp is not None and t["neighbors"].get("top") is not None:
            existing = canvas[y0:y0 + ov, x0:x0 + tile_size, :]
            a = ramp.reshape(-1, 1, 1)
            if blended is arr:
                blended = blended.copy()
            blended[:ov, :, :] = existing * (1 - a) + blended[:ov, :, :] * a

        canvas[y0:y0 + tile_size, x0:x0 + tile_size, :] = blended

    out_img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")
    out_img.save(out, quality=96)
    return {"width": out_img.width, "height": out_img.height}
