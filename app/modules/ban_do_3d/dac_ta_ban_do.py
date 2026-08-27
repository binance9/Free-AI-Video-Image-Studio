from __future__ import annotations
from dataclasses import dataclass, asdict, field
from hashlib import sha256
import re

BIOMES = {
    "rung": ("rừng", "forest", "jungle"), "tuyet": ("tuyết", "snow", "ice"),
    "sa_mac": ("sa mạc", "desert"), "dong_bang": ("đồng bằng", "plains", "grassland"),
    "nui_lua": ("núi lửa", "volcano", "lava"), "bien_dao": ("biển", "đảo", "coast", "island"),
    "lang": ("làng", "village"), "thanh": ("thành", "city", "castle"), "dungeon": ("dungeon", "hang", "hầm")
}

@dataclass
class MapSpec:
    prompt: str
    quality: str
    tile_count: int
    tile_size: int
    overlap_px: int
    seed: int
    style: str = "fantasy game map, crisp detailed, coherent world design"
    view: str = "isometric top-down"
    biomes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    reference_used: bool = False

    def as_dict(self): return asdict(self)


def parse_prompt(prompt: str, quality: str, cfg: dict, tile_count: int | None, reference_used: bool) -> MapSpec:
    text = (prompt or "").strip()
    if not text and not reference_used:
        raise ValueError("Cần mô tả map hoặc ảnh mẫu")
    low = text.lower()
    biomes = [k for k, keys in BIOMES.items() if any(x in low for x in keys)]
    constraints = []
    for token in ("giữ nguyên", "không đổi", "sông", "đường", "thành chính", "trung tâm", "cầu", "bờ biển"):
        if token in low: constraints.append(token)
    n = int(tile_count or cfg["tiles"])
    seed_src = f"{text}|{quality}|{n}|{reference_used}".encode("utf-8")
    seed = int(sha256(seed_src).hexdigest()[:8], 16)
    style = "fantasy game map, high-detail illustrated terrain"
    if re.search(r"\b(pixel|pixel art)\b", low): style = "crisp pixel-art game map"
    if "realistic" in low or "thực tế" in low: style = "realistic game world map"
    return MapSpec(text, quality, n, int(cfg["tile_size"]), int(cfg["overlap"]), seed, style, "isometric top-down", biomes, constraints, reference_used)
