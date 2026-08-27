"""Smoke test cho module nhan_vat_2d - nhanh, KHONG load model AI that.

Chay: pytest -q tests/smoke/test_nhan_vat_2d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_constructs(smoke_tmp_path):
    from app.modules.nhan_vat_2d import Character2DService, CharacterProfile
    from app.modules.nhan_vat_2d.api_nhan_vat_2d import router

    service = Character2DService(root=smoke_tmp_path / "nhan_vat_2d")
    assert service.root.exists()
    assert router.routes, "router phai co it nhat 1 route"
    profile = CharacterProfile.from_prompt("blue armor swordsman")
    assert profile is not None


def test_app_wires_character_2d_router(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/character-2d/status")
    assert resp.status_code != 404, "route /api/character-2d/status khong duoc dang ky"


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/nhan_vat_2d/nhan_vat_2d.js").is_file()
    assert (ROOT / "app/modules/nhan_vat_2d/README_MODULE.md").is_file()
