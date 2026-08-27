from __future__ import annotations

import json
from pathlib import Path
from PIL import Image


def export_sheet(cell_paths: list[Path], columns: int, output_png: Path, output_json: Path, labels: list[str]) -> dict:
    if not cell_paths:
        raise ValueError("Không có frame để ghép sheet")
    with Image.open(cell_paths[0]) as first:
        cell_w, cell_h = first.size
    rows = (len(cell_paths) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * cell_w, rows * cell_h), (0, 0, 0, 0))
    frames = []
    for idx, path in enumerate(cell_paths):
        with Image.open(path) as im:
            x = (idx % columns) * cell_w
            y = (idx // columns) * cell_h
            sheet.paste(im.convert("RGBA"), (x, y))
        frames.append({
            "index": idx,
            "label": labels[idx] if idx < len(labels) else str(idx),
            "file": path.name,
            "x": x,
            "y": y,
            "w": cell_w,
            "h": cell_h,
        })
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_png)
    output_json.write_text(json.dumps({"cell_width": cell_w, "cell_height": cell_h, "frames": frames}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"sheet": str(output_png), "meta": str(output_json), "frames": len(frames), "cell_width": cell_w, "cell_height": cell_h}
