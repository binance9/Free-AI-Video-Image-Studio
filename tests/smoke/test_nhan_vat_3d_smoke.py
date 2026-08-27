"""Smoke test cho module nhan_vat_3d - nhanh, KHONG dung 3D that.

Chay: pytest -q tests/smoke/test_nhan_vat_3d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports(smoke_tmp_path):
    from app.modules.nhan_vat_3d.service import Local3DService
    from app.modules.nhan_vat_3d.triposr_backend import TripoSRBackend
    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace
    from app.modules.nhan_vat_3d.api_nhan_vat_3d import router

    backend = TripoSRBackend(smoke_tmp_path / "missing_tool", smoke_tmp_path / "cache")
    status = backend.status()
    assert status["installed"] is False, "may test khong co TripoSR that - dung"

    workspace = Model3DWorkspace(smoke_tmp_path / "assets")
    assert workspace.root.exists()
    assert router.routes


def test_status_endpoint_does_not_error(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/3d/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "installed" in data


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/nhan_vat_3d/nhan_vat_3d.js").is_file()
    assert (ROOT / "web/modules/nhan_vat_3d/ai_3d_viewer.js").is_file()
    assert (ROOT / "web/modules/nhan_vat_3d/ai_3d_presets.js").is_file()
    assert (ROOT / "app/modules/nhan_vat_3d/README_MODULE.md").is_file()


def test_no_game_ready_business_logic_leaked_into_3d():
    js = (ROOT / "web/modules/nhan_vat_3d/nhan_vat_3d.js").read_text(encoding="utf-8")
    assert "pollGameReady" not in js
    assert "refreshGameReadyStatus" not in js
    py_files = (ROOT / "app/modules/nhan_vat_3d").glob("*.py")
    for f in py_files:
        assert "game_ready" not in f.read_text(encoding="utf-8"), f"{f} khong duoc chua logic game_ready"
