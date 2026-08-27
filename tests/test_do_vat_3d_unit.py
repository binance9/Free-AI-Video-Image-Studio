"""Unit test nhe cho do_vat_3d - KHONG goi AI that, KHONG can model/venv.

Chay: pytest -q tests/test_do_vat_3d_unit.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

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

def _build_minimal_glb(path, *, with_triangle=True, with_texture=False, scale=1.0) -> None:
    """Dung struct+json thuan de dung 1 file GLB toi thieu hop le theo dung
    glTF 2.0 binary spec - khong can trimesh. Dung tu dien (4 diem khong
    dong phang) de bounding box co gia tri that o ca 3 truc. scale nhan vao
    toa do de test bbox-volume-ratio (xem toi_uu_so_mat)."""
    positions = [c * scale for c in (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)]
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
            "min": [0.0, 0.0, 0.0], "max": [scale, scale, scale],
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


# ==================== Phase 1.6.1: poly target enforcement ====================

from app.modules.do_vat_3d.chon_engine import poly_target_cho
from app.modules.do_vat_3d.toi_uu_do_vat import toi_uu_so_mat


def test_poly_target_cho_matches_preset_defaults():
    assert poly_target_cho("tu_do", "lite") == 12_000
    assert poly_target_cho("thung", "standard") == 32_000  # no category floor for "thung"
    assert poly_target_cho("tu_do", "final") == 60_000


def test_poly_target_cho_category_floor_only_raises_when_above_preset():
    # "cay" (tree) floor 20_000 < preset standard target 32_000 -> floor is a no-op
    assert poly_target_cho("cay", "standard") == 32_000
    # floor never applies outside STANDARD, even if it would be "higher"
    assert poly_target_cho("cay", "lite") == 12_000


def test_lua_chon_engine_carries_poly_target_and_tolerance():
    choice = chon_engine_do_vat("da", "standard")
    assert choice.poly_target == 32_000
    assert 0 < choice.poly_tolerance < 1


# ---------- toi_uu_so_mat: fallback paths (no real trimesh needed - the
# subprocess call itself fails, so the pure-stdlib fallback path runs) ----------

def test_toi_uu_so_mat_skips_when_input_glb_invalid(tmp_path):
    bad = tmp_path / "shape.glb"
    _build_minimal_glb(bad, with_triangle=False)  # 0 triangles -> khong hop le
    out = tmp_path / "optimized.glb"
    result = toi_uu_so_mat(bad, out, 32_000, runtime_python=tmp_path / "no_python.exe")
    assert result.optimize_applied is False
    assert out.exists()
    assert result.error and "không hợp lệ" in result.error


def test_toi_uu_so_mat_falls_back_when_runtime_python_missing(tmp_path):
    src = tmp_path / "shape.glb"
    _build_minimal_glb(src, with_triangle=True)
    out = tmp_path / "optimized.glb"
    result = toi_uu_so_mat(src, out, 32_000, runtime_python=tmp_path / "does_not_exist.exe")
    assert result.optimize_applied is False
    assert result.optimized_triangle_count == result.original_triangle_count
    assert out.exists()
    assert out.read_bytes() == src.read_bytes()  # original preserved byte-for-byte
    assert "chưa cài Character HD runtime" in result.error


def test_toi_uu_so_mat_rejects_collapsed_bbox_and_keeps_original(tmp_path, monkeypatch):
    """Mo phong optimizer chinh chay xong nhung ra mesh bi sup bbox (loi
    thuat toan/du lieu) - toi_uu_so_mat phai tu reject va giu nguyen ban goc,
    KHONG dung ket qua nguy hiem (section 6)."""
    import sys
    from app.modules.do_vat_3d import toi_uu_do_vat as mod

    src = tmp_path / "shape.glb"
    _build_minimal_glb(src, with_triangle=True, scale=1.0)  # bbox volume = 1.0
    out = tmp_path / "optimized.glb"

    def fake_run(cmd, **kwargs):
        candidate_path = Path(cmd[3])
        _build_minimal_glb(candidate_path, with_triangle=True, scale=0.3)  # volume 0.027 -> ratio 0.027, ngoai [0.7,1.3]
        stdout = "AIVF_MESH_DECIMATE_OK " + json.dumps({"optimized": True, "optimizer": "trimesh-vertex-clustering"})

        class Done:
            returncode = 0
        d = Done()
        d.stdout = stdout
        d.stderr = ""
        return d

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    result = toi_uu_so_mat(src, out, 32_000, runtime_python=sys.executable)
    assert result.optimize_applied is False
    assert "bounding box lệch bất thường" in result.error
    assert out.read_bytes() == src.read_bytes()


def test_toi_uu_so_mat_accepts_valid_decimate_result(tmp_path, monkeypatch):
    import sys
    from app.modules.do_vat_3d import toi_uu_do_vat as mod

    src = tmp_path / "shape.glb"
    _build_minimal_glb(src, with_triangle=True, scale=1.0)
    out = tmp_path / "optimized.glb"

    def fake_run(cmd, **kwargs):
        candidate_path = Path(cmd[3])
        _build_minimal_glb(candidate_path, with_triangle=True, scale=1.05)  # ratio ~1.16, trong nguong an toan
        stdout = "AIVF_MESH_DECIMATE_OK " + json.dumps({"optimized": True, "optimizer": "trimesh-vertex-clustering"})

        class Done:
            returncode = 0
        d = Done()
        d.stdout = stdout
        d.stderr = ""
        return d

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    result = toi_uu_so_mat(src, out, 2, runtime_python=sys.executable, tolerance=0.15)
    assert result.optimize_applied is True
    assert result.error is None
    assert result.optimizer == "trimesh-vertex-clustering"
    assert result.original_triangle_count == 2
    assert result.optimized_triangle_count == 2


# ==================== Phase 1.6.1: shared GPU lock (queue/cancel) ====================

import threading
import time as _time

from app.core.shared_services import JobCancelled, heavy_gpu_job_lock, heavy_gpu_job_status


def test_heavy_gpu_job_lock_reports_owner_while_held():
    assert heavy_gpu_job_status()["current_owner"] is None
    with heavy_gpu_job_lock(owner="test_owner"):
        status = heavy_gpu_job_status()
        assert status["busy"] is True
        assert status["current_owner"] == "test_owner"
    assert heavy_gpu_job_status()["current_owner"] is None


def test_heavy_gpu_job_lock_second_caller_waits_then_reports_queue():
    entered_first = threading.Event()
    release_first = threading.Event()
    waited = []

    def hold_first():
        with heavy_gpu_job_lock(owner="first"):
            entered_first.set()
            release_first.wait(timeout=5)

    t = threading.Thread(target=hold_first, daemon=True)
    t.start()
    assert entered_first.wait(timeout=5)

    def on_wait(_):
        waited.append(True)

    def try_second():
        with heavy_gpu_job_lock(owner="second", on_wait=on_wait):
            pass

    t2 = threading.Thread(target=try_second, daemon=True)
    t2.start()
    _time.sleep(0.3)
    assert heavy_gpu_job_status()["queued_jobs"] >= 1
    assert waited == [True]
    release_first.set()
    t.join(timeout=5)
    t2.join(timeout=5)


def test_heavy_gpu_job_lock_cancel_while_waiting_raises_without_acquiring():
    release_first = threading.Event()
    entered_first = threading.Event()

    def hold_first():
        with heavy_gpu_job_lock(owner="first"):
            entered_first.set()
            release_first.wait(timeout=5)

    t = threading.Thread(target=hold_first, daemon=True)
    t.start()
    assert entered_first.wait(timeout=5)

    cancel_event = threading.Event()
    cancel_event.set()  # da huy TRUOC khi vao hang doi
    with pytest.raises(JobCancelled):
        with heavy_gpu_job_lock(owner="second", cancel_event=cancel_event):
            pass  # khong duoc vao day

    release_first.set()
    t.join(timeout=5)


# ==================== Phase 1.6.1: GameAsset3D poly metadata ====================

def test_game_asset_from_metadata_reads_poly_fields_when_present():
    meta = {
        "asset_id": "abc123def456", "category": "da", "name": "Đá 01", "engine": "quick",
        "quality": "standard", "has_texture": True, "poly_count": 31844, "vertices": 16000,
        "dimensions": {"x": 1.1, "y": 0.9, "z": 1.0}, "pivot": "bottom_center",
        "recommended_scale": {"min": 0.5, "max": 2.5, "note": "n"}, "game_ready": False,
        "poly": {
            "original_triangle_count": 129680, "optimized_triangle_count": 31844,
            "poly_target": 32000, "poly_target_met": True, "optimization_ratio": 0.2456,
            "optimizer": "trimesh-vertex-clustering",
        },
        "best_output_path": "/tmp/textured.glb",
    }
    asset = game_asset_from_metadata(meta, glb_path="/tmp/model.glb", thumbnail_path=None)
    assert asset.original_triangle_count == 129680
    assert asset.optimized_triangle_count == 31844
    assert asset.poly_target == 32000
    assert asset.poly_target_met is True
    assert asset.best_output_path == "/tmp/textured.glb"


def test_game_asset_from_metadata_defaults_poly_fields_when_absent():
    meta = {
        "asset_id": "abc123def456", "category": "da", "name": "Đá 01", "engine": "quick",
        "quality": "standard", "has_texture": False, "poly_count": 100, "vertices": 60,
        "dimensions": {"x": 1.0, "y": 1.0, "z": 1.0}, "pivot": "bottom_center",
        "recommended_scale": {"min": 0.5, "max": 2.5, "note": "n"}, "game_ready": False,
    }
    asset = game_asset_from_metadata(meta, glb_path="/tmp/model.glb", thumbnail_path=None)
    assert asset.original_triangle_count == 0
    assert asset.optimizer == "none"
    assert asset.best_output_path is None


# ==================== Phase 1.6.1: job manager partial_success + retry ====================

class _FakeService:
    """Gia lap DoVat3DService: khong goi AI that, chi tra ve du lieu gia
    lap co cau truc dung nhu dich_vu_do_vat_3d.DoVat3DService that."""

    def __init__(self):
        self.tao_do_vat_calls = 0
        self.to_mau_lai_calls = []

    def tao_do_vat(self, *, category, quality, texture_preset, work_dir, image_path=None,
                    prompt=None, low_vram=False, progress=None, cancel_event=None):
        self.tao_do_vat_calls += 1
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        shape_path = work_dir / "shape.glb"
        _build_minimal_glb(shape_path, with_triangle=True)
        image_for_texture = work_dir / "preprocessed.png"
        image_for_texture.write_bytes(b"\x89PNG\r\n\x1a\n")
        texture_error = "Paint HD quá thời gian tối đa 4 giờ. Mesh trắng gốc vẫn còn nguyên." if texture_preset != "none" else None
        return {
            "model_path": shape_path, "shape_path": shape_path, "optimized_path": None,
            "best_output_path": shape_path, "category": category, "category_label": category,
            "pivot": "bottom_center", "recommended_scale": {"min": 1, "max": 2, "note": "n"},
            "quality": quality, "texture_preset": texture_preset, "has_texture": False,
            "texture_error": texture_error, "texture_timed_out": bool(texture_error),
            "engine": "quick", "engine_label": "TripoSR", "engine_reason": "test",
            "triangle_count": 2, "vertex_count": 4, "dimensions": {"x": 1, "y": 1, "z": 1},
            "device": "cpu", "timings": {"total_seconds": 0.1},
            "poly": {
                "original_triangle_count": 2, "optimized_triangle_count": 2, "poly_target": 32000,
                "poly_target_met": False, "optimization_ratio": 1.0, "optimizer": "none", "optimize_error": None,
            },
        }

    def to_mau_lai(self, *, mesh_glb, image_path, work_dir, texture_preset, progress=None, cancel_event=None):
        self.to_mau_lai_calls.append({"mesh_glb": Path(mesh_glb), "image_path": Path(image_path), "texture_preset": texture_preset})
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        out = work_dir / "textured.glb"
        _build_minimal_glb(out, with_triangle=True)
        return {
            "model_path": out, "texture_preset": texture_preset, "has_texture": True,
            "texture_error": None, "texture_timed_out": False, "triangle_count": 2,
            "vertex_count": 4, "dimensions": {"x": 1, "y": 1, "z": 1}, "timings": {"total_seconds": 0.1},
        }


def _wait_status(jobs, job_id, terminal_statuses, timeout=5.0):
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        job = jobs.get(job_id)
        if job["status"] in terminal_statuses:
            return job
        _time.sleep(0.02)
    raise AssertionError(f"job did not reach {terminal_statuses} in time, last={jobs.get(job_id)}")


def test_job_manager_marks_partial_success_when_texture_times_out(tmp_path):
    from app.modules.do_vat_3d.quan_ly_job import DoVat3DJobManager
    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace

    service = _FakeService()
    workspace = Model3DWorkspace(tmp_path / "assets")
    jobs = DoVat3DJobManager(service, workspace, tmp_path / "jobs")

    job_id = jobs.start(category="da", quality="standard", texture_preset="lite",
                         image_path=_make_sample_image(tmp_path))
    job = _wait_status(jobs, job_id, {"partial_success", "done", "error"})
    assert job["status"] == "partial_success"
    assert job["result"]["texture_error"]
    assert "retry_info" in job and job["retry_info"]["mesh_for_texture"]


def test_job_manager_marks_done_when_no_texture_requested(tmp_path):
    from app.modules.do_vat_3d.quan_ly_job import DoVat3DJobManager
    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace

    service = _FakeService()
    workspace = Model3DWorkspace(tmp_path / "assets")
    jobs = DoVat3DJobManager(service, workspace, tmp_path / "jobs")

    job_id = jobs.start(category="da", quality="standard", texture_preset="none",
                         image_path=_make_sample_image(tmp_path))
    job = _wait_status(jobs, job_id, {"partial_success", "done", "error"})
    assert job["status"] == "done"


def test_job_manager_retry_texture_reuses_mesh_without_rerunning_shape(tmp_path):
    from app.modules.do_vat_3d.quan_ly_job import DoVat3DJobManager
    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace

    service = _FakeService()
    workspace = Model3DWorkspace(tmp_path / "assets")
    jobs = DoVat3DJobManager(service, workspace, tmp_path / "jobs")

    job_id = jobs.start(category="da", quality="standard", texture_preset="lite",
                         image_path=_make_sample_image(tmp_path))
    _wait_status(jobs, job_id, {"partial_success", "done", "error"})
    assert service.tao_do_vat_calls == 1

    jobs.retry_texture(job_id, "hd")
    job = _wait_status(jobs, job_id, {"partial_success", "done", "error"})
    assert job["status"] == "done"
    assert service.tao_do_vat_calls == 1  # KHONG dung lai shape/preprocess
    assert len(service.to_mau_lai_calls) == 1
    assert service.to_mau_lai_calls[0]["texture_preset"] == "hd"


def test_job_manager_retry_texture_rejects_when_no_prior_job_data(tmp_path):
    from app.modules.do_vat_3d.quan_ly_job import DoVat3DJobManager
    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace

    service = _FakeService()
    workspace = Model3DWorkspace(tmp_path / "assets")
    jobs = DoVat3DJobManager(service, workspace, tmp_path / "jobs")
    with pytest.raises(ValueError):
        jobs.retry_texture("0" * 32, "hd")


def _make_sample_image(tmp_path):
    img = tmp_path / "input.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return img
