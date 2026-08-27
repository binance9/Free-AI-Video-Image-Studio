"""Smoke test cho module nhan_vat_game_ready - nhanh, KHONG chay Blender that.

Neu may test khong co Blender, status phai bao "unavailable" ro rang va
TEST VAN PASS (khong fail vi thieu Blender).

Chay: pytest -q tests/smoke/test_nhan_vat_game_ready_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_status_is_blender_aware(smoke_tmp_path):
    from app.modules.nhan_vat_game_ready.service import GameReady3DService
    from app.modules.nhan_vat_game_ready.jobs import GameReadyJobManager
    from app.modules.nhan_vat_game_ready.api_nhan_vat_game_ready import router

    service = GameReady3DService(smoke_tmp_path / "game_ready")
    status = service.status()
    assert "installed" in status
    assert "message" in status
    assert "pipeline" in status
    # KHONG assert installed == True/False - may test co the co hoac khong co Blender.
    if not status["installed"]:
        assert "Blender" in status["message"] or "SETUP_GAME_READY_3D" in status["message"]
    assert router.routes


def test_status_endpoint_works_regardless_of_blender(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/3d/game-ready/status")
    assert resp.status_code == 200, "status endpoint khong duoc fail du Blender co hay khong"
    data = resp.json()
    assert "installed" in data


def test_frontend_assets_exist_and_are_separate_from_nhan_vat_3d():
    assert (ROOT / "web/modules/nhan_vat_game_ready/nhan_vat_game_ready.js").is_file()
    assert (ROOT / "web/modules/nhan_vat_game_ready/nhan_vat_game_ready.css").is_file()
    assert (ROOT / "app/modules/nhan_vat_game_ready/README_MODULE.md").is_file()
    js = (ROOT / "web/modules/nhan_vat_game_ready/nhan_vat_game_ready.js").read_text(encoding="utf-8")
    assert "pollGameReady" in js
    assert "refreshGameReadyStatus" in js


def test_index_html_loads_game_ready_assets_after_nhan_vat_3d():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    i3d = html.find("modules/nhan_vat_3d/nhan_vat_3d.js")
    igr = html.find("modules/nhan_vat_game_ready/nhan_vat_game_ready.js")
    assert i3d != -1 and igr != -1
    assert i3d < igr, "nhan_vat_game_ready.js phai load SAU nhan_vat_3d.js (phu thuoc window.AIVF3D)"
    assert "modules/nhan_vat_game_ready/nhan_vat_game_ready.css" in html


def test_convert_writes_fixed_final_filename_and_intermediate_stage_names():
    """Section 2: final file phai luon ten game_ready.glb, khong duoc dung
    ten ngau nhien - kiem tra bang cach doc code, khong chay Blender that."""
    src = (ROOT / "app/modules/nhan_vat_game_ready/service.py").read_text(encoding="utf-8")
    assert 'out_dir / "game_ready.glb"' in src
    blender_src = (ROOT / "app/modules/nhan_vat_game_ready/blender_game_ready.py").read_text(encoding="utf-8")
    for name in ('"source.glb"', '"optimized.glb"', '"rigged.glb"'):
        assert name in blender_src, f"thiếu checkpoint file {name}"


def test_validation_module_importable_and_schema_has_required_fields(smoke_tmp_path):
    from app.modules.nhan_vat_game_ready.validate_game_ready import (
        REQUIRED_CLIPS,
        validate_game_ready_glb,
    )
    assert set(REQUIRED_CLIPS) == {"idle", "run", "attack_01"}
    # File khong ton tai van phai tra ve ket qua co cau truc day du, khong crash.
    result = validate_game_ready_glb(smoke_tmp_path / "does_not_exist.glb")
    d = result.to_dict()
    for key in ("ok", "animation_ok", "errors", "skins_count", "has_joints_attr",
                "has_weights_attr", "weight_coverage", "required_clips_present"):
        assert key in d
    assert d["ok"] is False


def test_job_manager_status_vocabulary_includes_partial_success():
    """Section 32: skeleton co nhung animation fail phai la partial_success,
    khong duoc bao PASS gia - kiem tra code path ton tai."""
    src = (ROOT / "app/modules/nhan_vat_game_ready/jobs.py").read_text(encoding="utf-8")
    assert "partial_success" in src
    assert "animation_ok" in src
