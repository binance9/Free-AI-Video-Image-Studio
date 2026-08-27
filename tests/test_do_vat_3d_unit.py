"""Unit test nhe cho do_vat_3d - KHONG goi AI that, KHONG can model/venv.

Chay: pytest -q tests/test_do_vat_3d_unit.py
"""
from __future__ import annotations

import json
import struct

import pytest

from app.modules.do_vat_3d.chon_engine import chon_engine_do_vat
from app.modules.do_vat_3d.hop_dong_asset import GameAsset3D, game_asset_from_metadata, liet_ke_thu_vien
from app.modules.do_vat_3d.kiem_tra_do_vat import kiem_tra_glb
from app.modules.do_vat_3d.phan_loai_do_vat import (
    ThamSoKhongHopLe,
    sanitize_ten_asset,
    thong_tin_danh_muc,
    validate_category,
    validate_quality,
    validate_texture,
)
from app.modules.do_vat_3d.toi_uu_do_vat import can_chuan_hoa_pivot


# ---------- category / quality / texture validation ----------

def test_validate_category_accepts_known_and_rejects_unknown():
    assert validate_category("cay") == "cay"
    assert validate_category("  DA  ") == "da"
    with pytest.raises(ThamSoKhongHopLe):
        validate_category("khong_ton_tai")
    with pytest.raises(ThamSoKhongHopLe):
        validate_category("")


def test_validate_quality_accepts_known_and_rejects_unknown():
    assert validate_quality("lite") == "lite"
    assert validate_quality("STANDARD") == "standard"
    with pytest.raises(ThamSoKhongHopLe):
        validate_quality("ultra")


def test_validate_texture_accepts_known_and_rejects_unknown():
    assert validate_texture("none") == "none"
    assert validate_texture("HD") == "hd"
    with pytest.raises(ThamSoKhongHopLe):
        validate_texture("photoreal")


def test_all_13_categories_have_bottom_center_pivot_and_scale():
    for key in ["cay", "da", "co_bui", "ruong", "thung", "hang_rao", "cot", "den",
                "nha_nho", "cong", "tuong", "trang_tri", "tu_do"]:
        info = thong_tin_danh_muc(key)
        assert info["pivot"] == "bottom_center"
        assert info["recommended_scale"]["min"] > 0
        assert info["recommended_scale"]["max"] >= info["recommended_scale"]["min"]


# ---------- filename sanitize ----------

def test_sanitize_ten_asset_strips_diacritics_and_specials():
    assert sanitize_ten_asset("Cây sồi 01") == "C_y_s_i_01"
    assert sanitize_ten_asset("") == "do_vat"
    assert sanitize_ten_asset("   ") == "do_vat"
    assert sanitize_ten_asset("../../etc/passwd") == "etc_passwd"
    long_name = "a" * 200
    assert len(sanitize_ten_asset(long_name)) <= 60


# ---------- engine selector ----------

def test_engine_selector_lite_always_picks_quick():
    for cat in ["cay", "da", "nha_nho", "thung"]:
        choice = chon_engine_do_vat(cat, "lite")
        assert choice.engine == "quick"


def test_engine_selector_final_always_picks_character_hd():
    for cat in ["cay", "da", "nha_nho", "thung"]:
        choice = chon_engine_do_vat(cat, "final")
        assert choice.engine == "character_hd"


def test_engine_selector_standard_depends_on_complexity():
    simple = chon_engine_do_vat("da", "standard")
    complex_ = chon_engine_do_vat("cay", "standard")
    assert simple.engine == "quick"
    assert complex_.engine == "character_hd"


def test_engine_selector_rejects_unknown_category_or_quality():
    with pytest.raises(ThamSoKhongHopLe):
        chon_engine_do_vat("khong_ton_tai", "standard")
    with pytest.raises(ThamSoKhongHopLe):
        chon_engine_do_vat("da", "khong_ton_tai")


def test_low_vram_downgrades_final_texture_and_profile_but_keeps_engine():
    normal = chon_engine_do_vat("nha_nho", "final", low_vram=False)
    low = chon_engine_do_vat("nha_nho", "final", low_vram=True)
    assert normal.engine == low.engine == "character_hd"
    assert normal.mesh_profile == "hd"
    assert low.mesh_profile == "medium"
    assert normal.texture_default == "hd"
    assert low.texture_default == "lite"
    assert "VRAM" in low.reason


def test_low_vram_does_not_affect_lite_preset():
    lite_normal = chon_engine_do_vat("nha_nho", "lite", low_vram=False)
    lite_low = chon_engine_do_vat("nha_nho", "lite", low_vram=True)
    assert lite_normal.mesh_profile == lite_low.mesh_profile
    assert lite_normal.texture_default == lite_low.texture_default


# ---------- pivot normalization gating ----------

def test_pivot_normalize_only_needed_for_character_hd():
    assert can_chuan_hoa_pivot("character_hd") is True
    assert can_chuan_hoa_pivot("quick") is False


# ---------- GameAsset3D contract ----------

def test_game_asset_from_metadata_uses_only_real_saved_fields():
    meta = {
        "asset_id": "abc123def456",
        "category": "da",
        "name": "Đá 01",
        "engine": "quick",
        "quality": "standard",
        "has_texture": False,
        "poly_count": 12000,
        "vertices": 6000,
        "dimensions": {"x": 1.1, "y": 0.9, "z": 1.0},
        "pivot": "bottom_center",
        "recommended_scale": {"min": 0.5, "max": 2.5, "note": "đường kính game unit"},
        "game_ready": False,
    }
    asset = game_asset_from_metadata(meta, glb_path="/tmp/model.glb", thumbnail_path=None)
    assert isinstance(asset, GameAsset3D)
    assert asset.asset_id == "abc123def456"
    assert asset.triangle_count == 12000
    assert asset.pivot == "bottom_center"
    d = asset.to_dict()
    assert d["category"] == "da"
    assert d["thumbnail_path"] is None


def test_liet_ke_thu_vien_returns_empty_for_missing_dir(tmp_path=None):
    from pathlib import Path
    assert liet_ke_thu_vien(Path("C:/definitely/does/not/exist/xyz")) == []


# ---------- GLB validator (pure stdlib, khong can trimesh) ----------

def _build_minimal_glb(path, *, with_triangle=True, with_texture=False) -> None:
    """Dung struct+json thuan de dung 1 file GLB toi thieu hop le theo dung
    glTF 2.0 binary spec - khong can trimesh. Dung tu dien (4 diem khong
    dong phang) de bounding box co gia tri that o ca 3 truc."""
    positions = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    indices = [0, 1, 2, 0, 1, 3] if with_triangle else []
    pos_bytes = struct.pack("<12f", *positions)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices) if indices else b""
    # 4-byte align each buffer view per glTF spec.
    pad = (4 - len(idx_bytes) % 4) % 4
    idx_bytes_padded = idx_bytes + b"\x00" * pad
    bin_data = pos_bytes + idx_bytes_padded

    accessors = [
        {
            "bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3",
            "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0],
        },
    ]
    buffer_views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes)}]
    primitive = {"attributes": {"POSITION": 0}}
    if with_triangle:
        accessors.append({
            "bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR",
        })
        buffer_views.append({"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(idx_bytes)})
        primitive["indices"] = 1
    else:
        # De thu that "0 tam giac" ma van giu bounding box hop le: khai bao
        # 1 accessor indices co count=0 (0-length buffer view) thay vi bo
        # han indices - vi bo han indices se duoc glTF hieu la non-indexed
        # triangle (van hop le, chi khac cach dem).
        accessors.append({
            "bufferView": 0, "componentType": 5123, "count": 0, "type": "SCALAR",
        })
        primitive["indices"] = 1

    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "meshes": [{"primitives": [primitive]}],
    }
    if with_texture:
        doc["materials"] = [{"name": "m"}]
        doc["images"] = [{"uri": "tex.png"}]
        doc["textures"] = [{"source": 0}]

    json_bytes = json.dumps(doc).encode("utf-8")
    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total_len))
        f.write(struct.pack("<I4s", len(json_bytes), b"JSON"))
        f.write(json_bytes)
        f.write(struct.pack("<I4s", len(bin_data), b"BIN\x00"))
        f.write(bin_data)


def test_kiem_tra_glb_accepts_valid_triangle_mesh(tmp_path=None):
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        _build_minimal_glb(path, with_triangle=True)
        result = kiem_tra_glb(path)
        assert result.hop_le, result.ly_do_loi
        assert result.triangle_count == 2
        assert result.vertex_count == 4
        assert result.dimensions == {"x": 1.0, "y": 1.0, "z": 1.0}
        assert result.has_texture is False
    finally:
        os.unlink(path)


def test_kiem_tra_glb_detects_texture():
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        _build_minimal_glb(path, with_triangle=True, with_texture=True)
        result = kiem_tra_glb(path)
        assert result.hop_le
        assert result.has_texture is True
    finally:
        os.unlink(path)


def test_kiem_tra_glb_rejects_empty_mesh_no_triangles():
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        _build_minimal_glb(path, with_triangle=False)
        result = kiem_tra_glb(path)
        assert not result.hop_le
        assert any("Triangle" in e for e in result.ly_do_loi)
    finally:
        os.unlink(path)


def test_kiem_tra_glb_rejects_missing_file():
    result = kiem_tra_glb("C:/does/not/exist.glb")
    assert not result.hop_le
    assert "không tồn tại" in result.ly_do_loi[0]


def test_kiem_tra_glb_rejects_bad_magic():
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".glb")
    try:
        os.write(fd, b"NOTAGLB!" + b"\x00" * 200)
    finally:
        os.close(fd)
    try:
        result = kiem_tra_glb(path)
        assert not result.hop_le
    finally:
        os.unlink(path)
