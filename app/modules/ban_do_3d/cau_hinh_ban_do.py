from __future__ import annotations

QUALITY = {
    # "refine": co goi AI edit() tinh chinh tung tile hay khong. Da do that
    # bang so sanh truoc/sau (xem MODULE_STATUS.md): bo_cuc_tong bi crop rồi
    # phong to len cho tung tile nen TU NO hoi mem net - refine=False (dung
    # thang crop) con mem hon nua, KHONG lam nhanh du de danh doi. Vi vay ca
    # 3 muc deu refine=True; "Nhe" nhanh hon nho it tile hon + tile_size nho
    # hon, khong phai nho bo qua AI refine.
    "lite": {"label": "Nhẹ", "tiles": 4, "tile_size": 1024, "ai_quality": "medium", "overlap": 96, "refine": True},
    "standard": {"label": "Trung bình", "tiles": 8, "tile_size": 1024, "ai_quality": "high", "overlap": 128, "refine": True},
    "final": {"label": "Đẹp", "tiles": 12, "tile_size": 2048, "ai_quality": "high", "overlap": 160, "refine": True},
}
LEGACY = {"nhe": "lite", "chuan": "standard", "dep": "final", "medium": "standard", "high": "final"}
ALLOWED_TILES = (4, 6, 8, 10, 12, 16, 20)

def resolve_quality(value: str | None) -> tuple[str, dict]:
    key = (value or "standard").strip().lower()
    key = LEGACY.get(key, key)
    if key not in QUALITY:
        raise ValueError("Chất lượng map phải là Nhẹ, Trung bình hoặc Đẹp")
    return key, dict(QUALITY[key])
