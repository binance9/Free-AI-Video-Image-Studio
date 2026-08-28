from __future__ import annotations

QUALITY = {
    # "refine": co goi AI edit() tinh chinh tung tile hay khong. Da do that
    # bang so sanh truoc/sau (xem MODULE_STATUS.md): bo_cuc_tong bi crop rồi
    # phong to len cho tung tile nen TU NO hoi mem net - refine=False (dung
    # thang crop) con mem hon nua, KHONG lam nhanh du de danh doi. Vi vay ca
    # 3 muc deu refine=True; "Nhe" nhanh hon nho it tile hon + tile_size nho
    # hon, khong phai nho bo qua AI refine.
    # Da do that (xem MODULE_STATUS.md, muc "sharpness gate - do that"):
    # sharpness_score dao dong RAT MANH giua cac lan chay ngay ca cung 1
    # config (0.147-0.343 voi ai_quality=medium+tile_retries=1; 0.167-0.271
    # voi cac bien the tang buoc/tang retry) - tang so buoc denoise ("high"
    # = 24 buoc) hay tang tile_retries len 2 deu KHONG cai thien on dinh, chi
    # lam "lite" cham hon nhieu (~13-20 phut thay vi ~7-9 phut) ma khong chac
    # chan vuot nguong. Giu ai_quality=medium + tile_retries=1 de "lite" dung
    # nghia la nhanh; sharpness van duoc cai thien that su nho strength=0.85
    # (dich_vu_ban_do.py, xem comment tai do) so voi strength=0.58 cu (~0.147
    # co dinh moi lan) - van con dao dong quanh nguong 0.35, chua dam bao
    # PASS 100% (xem MODULE_STATUS.md de biet gioi han da biet).
    "lite": {"label": "Nhẹ", "tiles": 4, "tile_size": 1024, "ai_quality": "medium", "overlap": 96, "refine": True, "tile_retries": 1},
    "standard": {"label": "Trung bình", "tiles": 8, "tile_size": 1024, "ai_quality": "high", "overlap": 128, "refine": True, "tile_retries": 1},
    "final": {"label": "Đẹp", "tiles": 12, "tile_size": 2048, "ai_quality": "high", "overlap": 192, "refine": True, "tile_retries": 2},
}
LEGACY = {"nhe": "lite", "chuan": "standard", "dep": "final", "medium": "standard", "high": "final"}
ALLOWED_TILES = (4, 6, 8, 10, 12, 16, 20)

def resolve_quality(value: str | None) -> tuple[str, dict]:
    key = (value or "standard").strip().lower()
    key = LEGACY.get(key, key)
    if key not in QUALITY:
        raise ValueError("Chất lượng map phải là Nhẹ, Trung bình hoặc Đẹp")
    return key, dict(QUALITY[key])
