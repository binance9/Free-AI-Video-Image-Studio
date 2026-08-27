"""Hang so cau hinh cho module do_vat_3d: nhom danh muc, preset chat luong,
preset texture. Khong chua logic AI - chi la du lieu tinh de cac file khac
(phan_loai_do_vat.py, chon_engine.py, dich_vu_do_vat_3d.py) tra cuu.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DanhMucDoVat:
    key: str
    ten_hien_thi: str
    phuc_tap: bool  # True = vat the phuc tap (silhouette chi tiet), False = don gian
    pivot: str
    recommended_scale_min: float
    recommended_scale_max: float
    scale_note: str


DANH_MUC: dict[str, DanhMucDoVat] = {
    "cay": DanhMucDoVat("cay", "Cây", True, "bottom_center", 4.0, 8.0, "chiều cao game unit"),
    "da": DanhMucDoVat("da", "Đá", False, "bottom_center", 0.5, 2.5, "đường kính game unit"),
    "co_bui": DanhMucDoVat("co_bui", "Cỏ / bụi", False, "bottom_center", 0.3, 1.0, "chiều cao game unit"),
    "ruong": DanhMucDoVat("ruong", "Rương", False, "bottom_center", 0.8, 1.2, "chiều cao game unit"),
    "thung": DanhMucDoVat("thung", "Thùng", False, "bottom_center", 0.8, 1.2, "chiều cao game unit"),
    "hang_rao": DanhMucDoVat("hang_rao", "Hàng rào", False, "bottom_center", 1.0, 2.0, "chiều dài đoạn game unit"),
    "cot": DanhMucDoVat("cot", "Cột", False, "bottom_center", 2.0, 4.0, "chiều cao game unit"),
    "den": DanhMucDoVat("den", "Đèn", False, "bottom_center", 1.5, 3.0, "chiều cao game unit"),
    "nha_nho": DanhMucDoVat("nha_nho", "Nhà nhỏ", True, "bottom_center", 4.0, 8.0, "chiều cao game unit"),
    "cong": DanhMucDoVat("cong", "Cổng", True, "bottom_center", 3.0, 6.0, "chiều cao game unit"),
    "tuong": DanhMucDoVat("tuong", "Tượng", True, "bottom_center", 2.0, 4.0, "chiều cao game unit"),
    "trang_tri": DanhMucDoVat("trang_tri", "Trang trí", False, "bottom_center", 0.3, 1.0, "chiều cao game unit"),
    "tu_do": DanhMucDoVat("tu_do", "Tự do", True, "bottom_center", 1.0, 4.0, "không cố định - xem dimensions thật"),
}

DANH_MUC_MAC_DINH = "tu_do"

# quality preset -> (backend uu tien cho vat don gian, backend uu tien cho vat phuc tap,
#                     resolution, mesh_profile, texture preset mac dinh, poly target ~tam giac)
QUALITY_PRESETS: dict[str, dict] = {
    "lite": {
        "label": "Nháp nhanh",
        "resolution": 160,
        "mesh_profile": "light",
        "texture_default": "none",
        "poly_target_min": 5_000,
        "poly_target_max": 15_000,
        "poly_target": 12_000,
        "timeout_seconds": 240,
    },
    "standard": {
        "label": "Chuẩn",
        "resolution": 256,
        "mesh_profile": "medium",
        "texture_default": "lite",
        "poly_target_min": 15_000,
        "poly_target_max": 40_000,
        "poly_target": 32_000,
        "timeout_seconds": 600,
    },
    "final": {
        "label": "Final",
        "resolution": 256,
        "mesh_profile": "hd",
        "texture_default": "hd",
        "poly_target_min": 40_000,
        "poly_target_max": 80_000,
        "poly_target": 60_000,
        "timeout_seconds": 1200,
    },
}
QUALITY_MAC_DINH = "standard"

# Dung sai cho phep khi enforce poly_target (xem toi_uu_do_vat.toi_uu_so_mat).
POLY_TOLERANCE = 0.15

# San toi thieu tam giac cho STANDARD theo tung category - bao ve silhouette
# (canh cay, mai nha, chan cot...) khoi bi optimizer nen qua tay. Chi ap dung
# khi poly_target tinh ra (tu QUALITY_PRESETS) thap hon san nay; khong dung
# de RAISE muc final/lite. Danh muc khong co trong day dung poly_target mac
# dinh cua preset, khong co san rieng.
POLY_FLOOR_STANDARD: dict[str, int] = {
    "cay": 20_000,      # tree - canh la de gay
    "nha_nho": 25_000,  # house - mai/chan nha
    "da": 10_000,       # rock - khoi don gian, san thap hon
    "ruong": 8_000,     # chest - hop don gian
    "cong": 20_000,     # cong - silhouette phuc tap nhu nha
}

# Timeout rieng cho stage texture (giay) - vuot qua thi huy texture, GIU
# nguyen shape/optimized mesh da co (xem dich_vu_do_vat_3d.py section TEXTURE).
TEXTURE_TIMEOUT_SECONDS: dict[str, int] = {
    "lite": 600,   # 10 phut
    "hd": 1800,    # 30 phut
}

# texture preset -> co to mau hay khong + backend paint dung
TEXTURE_PRESETS: dict[str, dict] = {
    "none": {"label": "Không tô màu", "apply_texture": False},
    "lite": {"label": "Tô màu nhanh", "apply_texture": True, "texture_quality": "lite"},
    "hd": {"label": "Tô màu chất lượng", "apply_texture": True, "texture_quality": "hd"},
}
TEXTURE_MAC_DINH = "lite"


def danh_sach_danh_muc() -> list[dict]:
    return [
        {
            "key": d.key,
            "ten_hien_thi": d.ten_hien_thi,
            "phuc_tap": d.phuc_tap,
            "pivot": d.pivot,
            "recommended_scale": {"min": d.recommended_scale_min, "max": d.recommended_scale_max, "note": d.scale_note},
        }
        for d in DANH_MUC.values()
    ]
