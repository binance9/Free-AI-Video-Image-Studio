from __future__ import annotations

from hashlib import sha256


def build_master_layout(spec: dict, width: int, height: int, reference: dict | None = None) -> dict:
    """Dữ liệu hình học toàn cục. Tile chỉ đọc phần giao bbox, không tự sinh feature."""
    text = (spec.get("prompt") or "").lower()
    features = []
    definitions = (
        ("road", ("đường", "road", "cầu"), [(0, 0.55), (1, 0.45)]),
        ("river", ("sông", "river", "hồ"), [(0.48, 0), (0.52, 1)]),
        ("coastline", ("biển", "bờ biển", "coast"), [(0.82, 0), (0.86, 1)]),
    )
    for kind, tokens, points in definitions:
        if any(token in text for token in tokens):
            features.append({"id": f"{kind}_global_01", "type": kind, "points": [{"x": round(x * width), "z": round(z * height)} for x, z in points]})
    zones = []
    for index, biome in enumerate(spec.get("biomes") or ["mixed"]):
        x0 = round(index * width / max(1, len(spec.get("biomes") or ["mixed"])))
        x1 = round((index + 1) * width / max(1, len(spec.get("biomes") or ["mixed"])))
        zones.append({"zone_id": f"zone_{index:02d}", "biome": biome, "bbox": {"x": x0, "z": 0, "width": x1 - x0, "height": height}})
    return {
        "version": 1, "layout_id": sha256(f"{spec['seed']}|{width}|{height}".encode()).hexdigest()[:16],
        "width": width, "height": height, "seed": spec["seed"], "locked": True,
        "terrain_only": True, "features": features, "zones": zones,
        "reference_analysis": reference or {},
    }


def enrich_tiles_from_layout(grid: dict, spec: dict, layout: dict) -> dict:
    step = spec["tile_size"] - spec["overlap_px"]
    for tile in grid["tiles"]:
        x, z = tile["col"] * step, tile["row"] * step
        bbox = {"x": x, "z": z, "width": spec["tile_size"], "height": spec["tile_size"]}
        tile["bbox"] = bbox
        tile["world_x"], tile["world_z"] = x, z
        tile["tile_seed"] = int(sha256(f"{spec['seed']}|{tile['tile_id']}".encode()).hexdigest()[:8], 16)
        tile["master_reference_region"] = dict(bbox)
        tile["biome"] = next((zone["biome"] for zone in layout["zones"] if zone["bbox"]["x"] < x + bbox["width"] and zone["bbox"]["x"] + zone["bbox"]["width"] > x), "mixed")
        for key, feature_type in (("road_segments", "road"), ("river_segments", "river"), ("coastline_segments", "coastline")):
            tile[key] = [feature for feature in layout["features"] if feature["type"] == feature_type and any(x <= point["x"] <= x + bbox["width"] and z <= point["z"] <= z + bbox["height"] for point in feature["points"])]
    return grid
