"""GameAsset3D - contract on dinh de module ban_do_3d (tuong lai) doc asset
do do_vat_3d tao ra, KHONG can biet internals (job manager, engine nao, file
nao). Day la ranh gioi chinh thuc giua 2 module.

Map sau nay CHI duoc doc qua contract nay (asset_id, glb_path, category,
dimensions, pivot, recommended_scale, metadata) - KHONG duoc doc thang file
asset.json/meta.json noi bo, vi cau truc file noi bo co the doi khi refactor
Phase 2 ma khong bao truoc cho ban_do_3d.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GameAsset3D:
    asset_id: str
    category: str
    display_name: str
    glb_path: str
    thumbnail_path: str | None
    triangle_count: int
    vertex_count: int
    dimensions: dict  # {"x":.., "y":.., "z":..}
    pivot: str
    recommended_scale: dict  # {"min":.., "max":.., "note":..}
    has_texture: bool
    engine: str
    quality: str
    game_ready: bool = False
    # Poly enforcement metadata (Phase 1.6.1) - tat ca deu la so lieu that,
    # khong fake; xem toi_uu_do_vat.toi_uu_so_mat.
    original_triangle_count: int = 0
    optimized_triangle_count: int = 0
    poly_target: int = 0
    poly_target_met: bool = False
    optimization_ratio: float = 1.0
    optimizer: str = "none"
    best_output_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def game_asset_from_metadata(meta: dict, *, glb_path: str | Path, thumbnail_path: str | Path | None) -> GameAsset3D:
    """Dung ket qua metadata (asset.json) da luu de dung GameAsset3D - KHONG
    fake bat ky field nao, tat ca lay tu du lieu that da luu."""
    return GameAsset3D(
        asset_id=meta["asset_id"],
        category=meta["category"],
        display_name=meta.get("name") or meta["category"],
        glb_path=str(glb_path),
        thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
        triangle_count=int(meta.get("poly_count") or 0),
        vertex_count=int(meta.get("vertices") or 0),
        dimensions=dict(meta.get("dimensions") or {}),
        pivot=meta.get("pivot", "bottom_center"),
        recommended_scale=dict(meta.get("recommended_scale") or {}),
        has_texture=bool(meta.get("has_texture", False)),
        engine=meta.get("engine", "unknown"),
        quality=meta.get("quality", "standard"),
        game_ready=bool(meta.get("game_ready", False)),
        original_triangle_count=int((meta.get("poly") or {}).get("original_triangle_count") or 0),
        optimized_triangle_count=int((meta.get("poly") or {}).get("optimized_triangle_count") or 0),
        poly_target=int((meta.get("poly") or {}).get("poly_target") or 0),
        poly_target_met=bool((meta.get("poly") or {}).get("poly_target_met") or False),
        optimization_ratio=float((meta.get("poly") or {}).get("optimization_ratio") or 1.0),
        optimizer=str((meta.get("poly") or {}).get("optimizer") or "none"),
        best_output_path=meta.get("best_output_path"),
    )


def liet_ke_thu_vien(workspace_root: str | Path) -> list[dict]:
    """Quet workspace do_vat_3d, doc asset.json cua tung asset da tao (khong
    dung database - chi la metadata JSON + duyet thu muc nhu section 21 yeu
    cau)."""
    root = Path(workspace_root)
    if not root.exists():
        return []
    items: list[dict] = []
    for folder in sorted(root.iterdir(), reverse=True):
        contract_path = folder / "asset.json"
        if not folder.is_dir() or not contract_path.exists():
            continue
        try:
            data = json.loads(contract_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta_path = folder / "meta.json"
        created_at = None
        if meta_path.exists():
            try:
                created_at = meta_path.stat().st_mtime
            except OSError:
                created_at = None
        items.append({**data, "created_at": created_at})
    return items
