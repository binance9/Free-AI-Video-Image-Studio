"""Smoke test cho module tai_video_web (tai video YouTube/web qua yt-dlp) -
nhanh, KHONG tai video that qua mang (xem ghi chu test that trong
MODULE_STATUS.md cho ket qua da chay thuc te bang video cong khai that).

Chay: pytest -q tests/smoke/test_tai_video_web_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_router_exists(smoke_tmp_path):
    from app.modules.tai_video_web import WebVideoDownloader, WebVideoJobManager
    from app.modules.tai_video_web.api_tai_video_web import router

    downloader = WebVideoDownloader(smoke_tmp_path / "output")
    assert downloader.output_dir.is_dir()
    assert router.routes


def test_status_endpoint_returns_200(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/tai-video-web/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert set(data["qualities"]) == {"360p", "720p", "1080p", "best"}


def test_rejects_invalid_url(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.post("/api/tai-video-web/jobs", json={"url": "not-a-url", "quality": "720p"})
    assert resp.status_code == 400


def test_rejects_bad_quality(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.post("/api/tai-video-web/jobs", json={"url": "https://example.com/v", "quality": "4k"})
    assert resp.status_code == 422  # pydantic pattern validation


def test_job_not_found_returns_404(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/tai-video-web/jobs/khong_ton_tai")
    assert resp.status_code == 404


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/tai_video_web/tai_video_web.js").is_file()
    assert (ROOT / "app/modules/tai_video_web/downloader.py").is_file()
    assert (ROOT / "app/modules/tai_video_web/api_tai_video_web.py").is_file()


def test_sidebar_has_no_small_result_preview_for_video_mode():
    """Yeu cau: 'khong tao preview nho ben phai' - sidebar KHONG duoc co the
    hien thi ket qua video (title/meta/thumbnail) nhu panel Facebook co -
    video xong phai vao thang khung editor lon."""
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    start = html.index('id="panel-taivideoweb"')
    end = html.index("MODULE: tai_video_web END")
    panel = html[start:end]
    assert "taiVideoWebResult" not in panel  # khong co the ket qua video rieng
    for required_id in ("taiVideoWebUrl", "taiVideoWebQuality", "taiVideoWebMode", "taiVideoWebDownloadBtn", "taiVideoWebProgress"):
        assert required_id in panel, f"thiếu control bắt buộc: {required_id}"


def test_frontend_js_is_separate_file_not_in_app_js():
    """Yeu cau: 'file tach rieng, khong nhet vao app.js'."""
    app_js = (ROOT / "web/core/app.js").read_text(encoding="utf-8")
    assert "tai-video-web" not in app_js
    assert "taiVideoWebDownloadBtn" not in app_js
    js = (ROOT / "web/modules/tai_video_web/tai_video_web.js").read_text(encoding="utf-8")
    assert "taiVideoWebDownloadBtn" in js
