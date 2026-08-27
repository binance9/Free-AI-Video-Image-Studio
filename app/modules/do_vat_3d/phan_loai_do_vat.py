"""Validate category/quality/texture preset va cac tham so dau vao khac cho
do_vat_3d. Tach rieng khoi dich_vu_do_vat_3d.py de test duoc doc lap, khong
can khoi tao service AI nao.
"""
from __future__ import annotations

import re

from .cau_hinh_do_vat import DANH_MUC, QUALITY_PRESETS, TEXTURE_PRESETS


class ThamSoKhongHopLe(ValueError):
    """Rai khi category/quality/texture khong ton tai trong danh sach ho tro."""


def validate_category(category: str) -> str:
    key = (category or "").strip().lower()
    if key not in DANH_MUC:
        allowed = ", ".join(sorted(DANH_MUC))
        raise ThamSoKhongHopLe(f"Loại đồ vật '{category}' không được hỗ trợ. Chọn một trong: {allowed}")
    return key


def validate_quality(quality: str) -> str:
    key = (quality or "").strip().lower()
    if key not in QUALITY_PRESETS:
        allowed = ", ".join(sorted(QUALITY_PRESETS))
        raise ThamSoKhongHopLe(f"Mức chất lượng '{quality}' không hợp lệ. Chọn một trong: {allowed}")
    return key


def validate_texture(texture: str) -> str:
    key = (texture or "").strip().lower()
    if key not in TEXTURE_PRESETS:
        allowed = ", ".join(sorted(TEXTURE_PRESETS))
        raise ThamSoKhongHopLe(f"Mức tô màu '{texture}' không hợp lệ. Chọn một trong: {allowed}")
    return key


def thong_tin_danh_muc(category: str) -> dict:
    key = validate_category(category)
    d = DANH_MUC[key]
    return {
        "key": d.key,
        "ten_hien_thi": d.ten_hien_thi,
        "phuc_tap": d.phuc_tap,
        "pivot": d.pivot,
        "recommended_scale": {"min": d.recommended_scale_min, "max": d.recommended_scale_max, "note": d.scale_note},
    }


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_\-]+")


def sanitize_ten_asset(raw: str, *, fallback: str = "do_vat") -> str:
    """Lam sach ten hien thi thanh 1 chuoi an toan de dat ten file (khong dau,
    khong ky tu dac biet). Dung cho ten file goi y, KHONG dung de tao duong
    dan tuyet doi (asset van luu theo asset_id ngau nhien, xem workspace)."""
    text = (raw or "").strip()
    if not text:
        return fallback
    cleaned = _SAFE_NAME.sub("_", text).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned[:60] or fallback
