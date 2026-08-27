"""Smoke test cho module chinh_sua_video (core video engine) - nhanh,
KHONG render video that.

Chay: pytest -q tests/smoke/test_chinh_sua_video_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_workspace_constructs(smoke_tmp_path):
    from app.modules.chinh_sua_video import VideoEditor
    from app.modules.chinh_sua_video.workspace import VideoWorkspace
    from app.modules.chinh_sua_video.api_chinh_sua_video import router

    editor = VideoEditor()
    workspace = VideoWorkspace(smoke_tmp_path / "editor", smoke_tmp_path / "stickers")
    assert editor is not None
    assert workspace.root.exists()
    assert router.routes


def test_app_wires_core_editor_routes(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    # editor/{id} voi session khong ton tai phai tra loi co kiem soat (khong 500)
    resp = client.get("/api/editor/does-not-exist")
    assert resp.status_code in (400, 404)
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200


def test_frontend_shared_shell_exists():
    assert (ROOT / "web/core/app.js").is_file()
    assert (ROOT / "web/modules/chinh_sua_video/emoji_picker.js").is_file()
    assert (ROOT / "app/modules/chinh_sua_video/README_MODULE.md").is_file()
