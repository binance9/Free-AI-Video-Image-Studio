"""Smoke test cho module do_vat_3d - nhanh, KHONG sinh 3D that (xem
tests/test_do_vat_3d_unit.py cho unit test chi tiet hon, va script test
that rieng neu can chay 1 asset don gian qua model cache co san).

Chay: pytest -q tests/smoke/test_do_vat_3d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_constructs(smoke_tmp_path):
    from app.modules.do_vat_3d import DoVat3DService, DoVat3DJobManager, GameAsset3D
    from app.modules.do_vat_3d.api_do_vat_3d import router

    service = DoVat3DService(
        smoke_tmp_path / "missing_tool", smoke_tmp_path / "cache", None, smoke_tmp_path
    )
    status = service.status()
    assert "installed" in status  # co the True/False tuy may test, khong assert cu the

    from app.modules.nhan_vat_3d.workspace import Model3DWorkspace
    workspace = Model3DWorkspace(smoke_tmp_path / "assets")
    jobs = DoVat3DJobManager(service, workspace, smoke_tmp_path / "jobs")
    assert jobs is not None
    assert GameAsset3D is not None
    assert router.routes


def test_status_endpoint_returns_200(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/do-vat-3d/status")
    assert resp.status_code == 200
    assert "installed" in resp.json()


def test_categories_endpoint_lists_13_categories(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/do-vat-3d/categories")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 13
    keys = {i["key"] for i in items}
    assert keys == {"cay", "da", "co_bui", "ruong", "thung", "hang_rao", "cot", "den",
                     "nha_nho", "cong", "tuong", "trang_tri", "tu_do"}


def test_assets_endpoint_empty_library_returns_200(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/do-vat-3d/assets")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_create_rejects_unsupported_category(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = client.post(
        "/api/do-vat-3d/create",
        files={"file": ("test.png", tiny_png, "image/png")},
        data={"category": "khong_ton_tai", "quality": "standard", "texture": "none"},
    )
    assert resp.status_code == 400


def test_create_from_prompt_rejects_unsupported_quality(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.post(
        "/api/do-vat-3d/create-from-prompt",
        json={"prompt": "a small wooden chest", "category": "ruong", "quality": "ultra_max", "texture": "none"},
    )
    assert resp.status_code == 400


def test_map_asset_contract_importable_and_parses():
    from app.modules.do_vat_3d.hop_dong_asset import GameAsset3D, game_asset_from_metadata
    meta = {
        "asset_id": "a" * 32, "category": "thung", "name": "Thùng gỗ",
        "engine": "quick", "quality": "standard", "has_texture": True,
        "poly_count": 8000, "vertices": 4200,
        "dimensions": {"x": 1.0, "y": 1.0, "z": 1.0},
        "pivot": "bottom_center",
        "recommended_scale": {"min": 0.8, "max": 1.2, "note": "chiều cao game unit"},
        "game_ready": False,
    }
    asset = game_asset_from_metadata(meta, glb_path="model.glb", thumbnail_path=None)
    assert isinstance(asset, GameAsset3D)
    assert asset.category == "thung"


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/do_vat_3d/do_vat_3d.js").is_file()
    assert (ROOT / "web/modules/do_vat_3d/do_vat_3d.css").is_file()
    assert (ROOT / "app/modules/do_vat_3d/README_MODULE.md").is_file()


def test_no_engine_business_logic_duplicated_from_nhan_vat_3d():
    """do_vat_3d PHAI goi lai Local3DService/TripoSRBackend/CharacterHDBackend
    cua nhan_vat_3d qua import, KHONG duoc copy code dung mesh."""
    py_files = list((ROOT / "app/modules/do_vat_3d").glob("*.py"))
    combined = "\n".join(f.read_text(encoding="utf-8") for f in py_files)
    assert "from app.modules.nhan_vat_3d.service import Local3DService" in combined
    # Khong duoc tu viet subprocess goi TripoSR/Hunyuan runner truc tiep -
    # phai di qua Local3DService.
    assert "run_character_hd.py" not in combined
    assert "run.py" not in combined  # ten script chay TripoSR
