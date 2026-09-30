from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageStat

from .chia_o_ban_do import grid_for_count


QUALITY_TARGET = {"lite": 1400, "standard": 1050, "final": 800}
QUALITY_OVERLAP = {"lite": 64, "standard": 96, "final": 128}
ALLOWED_CHUNKS = (4, 8, 12, 16, 20, 24, 30, 36)


def choose_chunk_count(width: int, height: int, quality: str) -> int:
    """Chọn số chunk theo diện tích HD và mức zoom, không hard-code một giá trị."""
    target = QUALITY_TARGET.get(quality, QUALITY_TARGET["standard"])
    raw = max(4, math.ceil(width / target) * math.ceil(height / target))
    return next((value for value in ALLOWED_CHUNKS if value >= raw), ALLOWED_CHUNKS[-1])


def _edges(total: int, cells: int) -> list[int]:
    return [round(index * total / cells) for index in range(cells + 1)]


def _biome_for(row: int, col: int, biomes: list[str]) -> str:
    return biomes[(row + col) % len(biomes)] if biomes else "mixed"


def _connections(chunk_id: str, bbox: dict, neighbors: dict, features: list[str]) -> tuple[list[dict], list[dict]]:
    entries, exits = [], []
    for side, neighbor in neighbors.items():
        if not neighbor:
            continue
        if side in ("left", "right"):
            point = {"x": bbox["x"] if side == "left" else bbox["x"] + bbox["width"], "z": bbox["z"] + bbox["height"] // 2}
        else:
            point = {"x": bbox["x"] + bbox["width"] // 2, "z": bbox["z"] if side == "top" else bbox["z"] + bbox["height"]}
        for feature in features:
            item = {"feature": feature, "side": side, "world_x": point["x"], "world_z": point["z"], "neighbor": neighbor}
            (entries if side in ("left", "top") else exits).append(item)
    return entries, exits


def split_master_map(*, master_path: Path, out_dir: Path, source_map_id: str, quality: str, seed: int, biomes: list[str], constraints: list[str], tile_manifest: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(master_path) as source:
        master = source.convert("RGB")
    width, height = master.size
    count = choose_chunk_count(width, height, quality)
    rows, cols = grid_for_count(count, width / max(1, height))
    # Chỉ dùng grid đầy đủ để bảo đảm phủ kín hình chữ nhật, không có ô khuyết.
    count = rows * cols
    overlap = min(QUALITY_OVERLAP.get(quality, 96), width // max(2, cols * 4), height // max(2, rows * 4))
    xs, zs = _edges(width, cols), _edges(height, rows)
    features = [name for name, tokens in (("road", ("đường", "road", "cầu")), ("river", ("sông", "river")), ("coast", ("bờ biển", "coast"))) if any(token in " ".join(constraints).lower() for token in tokens)]
    chunks = []

    for row in range(rows):
        for col in range(cols):
            chunk_id = f"chunk_{row:02d}_{col:02d}"
            x0, x1, z0, z1 = xs[col], xs[col + 1], zs[row], zs[row + 1]
            crop_box = (max(0, x0 - overlap), max(0, z0 - overlap), min(width, x1 + overlap), min(height, z1 + overlap))
            neighbors = {
                "left": f"chunk_{row:02d}_{col-1:02d}" if col else None,
                "right": f"chunk_{row:02d}_{col+1:02d}" if col + 1 < cols else None,
                "top": f"chunk_{row-1:02d}_{col:02d}" if row else None,
                "bottom": f"chunk_{row+1:02d}_{col:02d}" if row + 1 < rows else None,
            }
            bbox = {"x": x0, "z": z0, "width": x1 - x0, "height": z1 - z0}
            entries, exits = _connections(chunk_id, bbox, neighbors, features)
            chunk_dir = out_dir / chunk_id
            chunk_dir.mkdir(parents=True, exist_ok=True)
            master.crop(crop_box).save(chunk_dir / "map.png", optimize=True)
            manifest = {
                "chunk_id": chunk_id, "row": row, "col": col,
                "world_x": x0, "world_z": z0, "width": x1 - x0, "height": z1 - z0,
                "overlap": overlap, "bbox": bbox,
                "crop_bbox": {"x": crop_box[0], "z": crop_box[1], "width": crop_box[2] - crop_box[0], "height": crop_box[3] - crop_box[1]},
                "core_offset": {"x": x0 - crop_box[0], "z": z0 - crop_box[1]},
                "neighbors": neighbors, "biome": _biome_for(row, col, biomes),
                "entry_points": entries, "exit_points": exits,
                "roads": [point for point in entries + exits if point["feature"] == "road"],
                "rivers": [point for point in entries + exits if point["feature"] == "river"],
                "spawn_points": [], "object_refs": [], "source_map_id": source_map_id,
                "tile_refs": [tile["tile_id"] for tile in (tile_manifest or {}).get("tiles", []) if tile.get("bbox", {}).get("x", 0) < x1 and tile.get("bbox", {}).get("x", 0) + tile.get("bbox", {}).get("width", 0) > x0 and tile.get("bbox", {}).get("z", 0) < z1 and tile.get("bbox", {}).get("z", 0) + tile.get("bbox", {}).get("height", 0) > z0],
            }
            (chunk_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (chunk_dir / "objects.json").write_text(json.dumps({"schema": {"asset_id": "string", "world_x": "number", "world_y": "number", "world_z": "number", "rotation": "number", "scale": "number", "chunk_id": "string"}, "objects": []}, ensure_ascii=False, indent=2), encoding="utf-8")
            (chunk_dir / "collision.json").write_text(json.dumps({"version": 1, "status": "future", "shapes": []}, indent=2), encoding="utf-8")
            (chunk_dir / "terrain.json").write_text(json.dumps({"version": 1, "status": "future", "layers": []}, indent=2), encoding="utf-8")
            chunks.append(manifest)

    global_manifest = {
        "version": 1, "source_map_id": source_map_id, "map_seed": seed, "quality": quality,
        "source": "map_nen_full_hd.png", "source_of_truth": True, "generated_from_prompt": False, "generated_from_hd_tiles": True,
        "world_bounds": {"x": 0, "z": 0, "width": width, "height": height},
        "artifacts": {"master_map": "ban_do_day_du.png", "map_spec": "map_spec.json", "master_layout": "bo_cuc_tong.png", "tile_manifest": "manifest_tiles.json"},
        "rows": rows, "cols": cols, "chunk_count": len(chunks), "overlap": overlap,
        "split_strategy": "quality-and-resolution grid; crop from full HD stitched from generated tiles",
        "chunks": chunks,
    }
    (out_dir.parent / "map_chunks_manifest.json").write_text(json.dumps(global_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return global_manifest


def rebuild_from_chunks(*, chunks_dir: Path, manifest: dict, output_path: Path) -> dict:
    bounds = manifest["world_bounds"]
    rebuilt = Image.new("RGB", (bounds["width"], bounds["height"]))
    for chunk in manifest["chunks"]:
        with Image.open(chunks_dir / chunk["chunk_id"] / "map.png") as image:
            core = image.convert("RGB").crop((chunk["core_offset"]["x"], chunk["core_offset"]["z"], chunk["core_offset"]["x"] + chunk["width"], chunk["core_offset"]["z"] + chunk["height"]))
        rebuilt.paste(core, (chunk["world_x"], chunk["world_z"]))
    rebuilt.save(output_path, optimize=True)
    return {"width": rebuilt.width, "height": rebuilt.height}


def validate_chunks(*, master_path: Path, rebuilt_path: Path, manifest: dict) -> dict:
    with Image.open(master_path) as master_image, Image.open(rebuilt_path) as rebuilt_image:
        master, rebuilt = master_image.convert("RGB"), rebuilt_image.convert("RGB")
        if master.size != rebuilt.size:
            similarity = 0.0
        else:
            difference = ImageStat.Stat(ImageChops.difference(master, rebuilt)).mean
            similarity = max(0.0, 1.0 - sum(difference) / (3 * 255))
    area = sum(chunk["width"] * chunk["height"] for chunk in manifest["chunks"])
    expected_area = manifest["world_bounds"]["width"] * manifest["world_bounds"]["height"]
    by_id = {chunk["chunk_id"]: chunk for chunk in manifest["chunks"]}
    reciprocal = True
    opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
    coordinate_links = True
    for chunk in manifest["chunks"]:
        for side, neighbor_id in chunk["neighbors"].items():
            if not neighbor_id:
                continue
            neighbor = by_id.get(neighbor_id)
            reciprocal &= bool(neighbor and neighbor["neighbors"].get(opposite[side]) == chunk["chunk_id"])
            mine = chunk["entry_points"] + chunk["exit_points"]
            theirs = (neighbor or {}).get("entry_points", []) + (neighbor or {}).get("exit_points", [])
            for point in mine:
                if point["neighbor"] == neighbor_id:
                    coordinate_links &= any(other["neighbor"] == chunk["chunk_id"] and other["feature"] == point["feature"] and other["world_x"] == point["world_x"] and other["world_z"] == point["world_z"] for other in theirs)
    passed = area == expected_area and reciprocal and coordinate_links and similarity >= 0.999
    return {"coverage_score": round(area / max(1, expected_area), 4), "rebuild_similarity": round(similarity, 6), "neighbors_reciprocal": reciprocal, "feature_coordinates_match": coordinate_links, "pass": passed}
