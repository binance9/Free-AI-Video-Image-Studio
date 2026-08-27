"""Smoke test cho module tai_video (tai video Facebook cong khai) - nhanh,
KHONG tai video that.

Chay: pytest -q tests/smoke/test_tai_video_smoke.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_url_validation(smoke_tmp_path):
    from app.modules.tai_video import FacebookVideoDownloader, FacebookVideoJobManager, FacebookVideoDownloadError
    from app.modules.tai_video.api_tai_video import router

    downloader = FacebookVideoDownloader(smoke_tmp_path / "downloads")
    assert downloader.library_dir.exists()
    assert downloader.validate_url("https://www.facebook.com/watch/?v=123") == "https://www.facebook.com/watch/?v=123"
    with pytest.raises(FacebookVideoDownloadError):
        downloader.validate_url("https://youtube.com/watch?v=123")
    assert router.routes


def test_app_wires_status_route(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/facebook-video/status")
    assert resp.status_code == 200
    assert "available" in resp.json()


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/tai_video/tai_video.js").is_file()
    assert (ROOT / "app/modules/tai_video/README_MODULE.md").is_file()
