"""Chon engine 3D tu dong cho do_vat_3d: nhanh nhat co the nhung khong pha
form. Khong hard-code mu - quyet dinh dua tren do phuc tap cua category va
preset chat luong nguoi dung chon.

Day KHONG phai engine that - chi la logic CHON giua 2 backend co san trong
app.modules.nhan_vat_3d (quick=TripoSR, character_hd=Hunyuan3D). Backend
that van nam nguyen o nhan_vat_3d, khong duplicate o day.
"""
from __future__ import annotations

from dataclasses import dataclass

from .cau_hinh_do_vat import DANH_MUC, POLY_FLOOR_STANDARD, POLY_TOLERANCE, QUALITY_PRESETS
from .phan_loai_do_vat import validate_category, validate_quality


@dataclass(frozen=True)
class LuaChonEngine:
    engine: str  # "quick" (TripoSR) hoac "character_hd" (Hunyuan3D)
    engine_label: str
    reason: str
    resolution: int
    mesh_profile: str
    texture_default: str
    poly_target_min: int
    poly_target_max: int
    poly_target: int
    poly_tolerance: float
    timeout_seconds: int


def poly_target_cho(category: str, quality: str) -> int:
    """Tinh poly_target thuc te cho 1 category+quality: lay poly_target cua
    preset, sau do ap dung san toi thieu rieng cua category (chi cho STANDARD,
    chi khi san CAO HON gia tri preset - khong bao gio ha thap hon)."""
    cat_key = validate_category(category)
    quality_key = validate_quality(quality)
    target = int(QUALITY_PRESETS[quality_key]["poly_target"])
    if quality_key == "standard":
        floor = POLY_FLOOR_STANDARD.get(cat_key)
        if floor and floor > target:
            target = int(floor)
    return target


def chon_engine_do_vat(category: str, quality: str, *, low_vram: bool = False) -> LuaChonEngine:
    cat_key = validate_category(category)
    quality_key = validate_quality(quality)
    cat = DANH_MUC[cat_key]
    preset = QUALITY_PRESETS[quality_key]

    if quality_key == "lite":
        # Nhap nhanh: luon uu tien engine nhe de test form nhanh nhat,
        # bat ke vat the don gian hay phuc tap.
        engine = "quick"
        reason = "Preset NHÁP NHANH luôn ưu tiên engine nhẹ (TripoSR) để test form nhanh nhất."
    elif quality_key == "final":
        # Final: da chot asset, uu tien chat luong cao nhat co the.
        engine = "character_hd"
        reason = "Preset FINAL ưu tiên engine chất lượng cao (Character HD/Hunyuan3D) cho asset đã chốt."
    else:
        # Chuan: quyet dinh theo do phuc tap silhouette cua category.
        if cat.phuc_tap:
            engine = "character_hd"
            reason = f"Đồ vật loại '{cat.ten_hien_thi}' có silhouette phức tạp (cành/mái/chi tiết) -> dùng engine chất lượng cao hơn để không phá form."
        else:
            engine = "quick"
            reason = f"Đồ vật loại '{cat.ten_hien_thi}' hình khối đơn giản -> dùng engine nhanh (TripoSR) là đủ tốt."

    mesh_profile = preset["mesh_profile"]
    resolution = preset["resolution"]
    texture_default = preset["texture_default"]
    timeout_seconds = preset["timeout_seconds"]

    if low_vram and engine == "character_hd" and quality_key != "lite":
        # VRAM thap: khong am tham doi engine ma chi ha mesh_profile/texture,
        # van giu engine da chon vi day la thu tu uu tien "khong pha form".
        mesh_profile = "medium" if mesh_profile == "hd" else mesh_profile
        texture_default = "lite" if texture_default == "hd" else texture_default
        reason += " (VRAM thấp: đã hạ mesh_profile/texture để tránh job quá lâu, vẫn giữ engine đã chọn)"

    return LuaChonEngine(
        engine=engine,
        engine_label="TripoSR · Nhanh" if engine == "quick" else "Hunyuan3D (Character HD) · Chi tiết",
        reason=reason,
        resolution=resolution,
        mesh_profile=mesh_profile,
        texture_default=texture_default,
        poly_target_min=preset["poly_target_min"],
        poly_target_max=preset["poly_target_max"],
        poly_target=poly_target_cho(cat_key, quality_key),
        poly_tolerance=POLY_TOLERANCE,
        timeout_seconds=timeout_seconds,
    )
