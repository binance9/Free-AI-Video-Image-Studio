"""Smoke test cho module tao_anh_ai - nhanh, KHONG sinh anh AI that.

Chay: pytest -q tests/smoke/test_tao_anh_ai_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_constructs(smoke_tmp_path):
    from app.modules.tao_anh_ai import AiImageWorkspace, LocalImageService, AiImageJobManager
    from app.modules.tao_anh_ai.api_tao_anh_ai import router

    service = LocalImageService("stable-diffusion-v1-5/stable-diffusion-v1-5", smoke_tmp_path / "model")
    workspace = AiImageWorkspace(smoke_tmp_path / "images")
    jobs = AiImageJobManager(service, workspace)
    assert service._text_pipe is None, "constructor khong duoc load pipeline ngay"
    assert workspace.root.exists()
    assert jobs is not None
    assert router.routes


def test_app_wires_route(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/ai-image/does-not-exist")
    assert resp.status_code != 500


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/tao_anh_ai/tao_anh_ai.js").is_file()
    assert (ROOT / "app/modules/tao_anh_ai/README_MODULE.md").is_file()
