"""Smoke test cho module cat_video (cắt video độc lập) - nhanh,
KHONG render video that.

Chay: pytest -q tests/smoke/test_cat_video_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_router_exists():
    from app.modules.cat_video import cut_video
    from app.modules.cat_video.service import cut_video as service_cut_video
    from app.modules.cat_video.api_cat_video import router

    assert cut_video is service_cut_video
    assert router.routes


def test_no_import_from_chinh_sua_video_in_engine_files():
    """cat_video's own engine (errors/ffmpeg_tools/probe/service) must stay
    fully independent of chinh_sua_video - only api_cat_video.py is allowed
    to touch chinh_sua_video (for the shared editor session/workspace)."""
    engine_files = ["errors.py", "ffmpeg_tools.py", "probe.py", "service.py", "schemas.py"]
    for name in engine_files:
        lines = (ROOT / "app" / "modules" / "cat_video" / name).read_text(encoding="utf-8").splitlines()
        import_lines = [ln for ln in lines if ln.strip().startswith(("import ", "from "))]
        assert not any("chinh_sua_video" in ln for ln in import_lines), (
            f"{name} phải độc lập, không import chinh_sua_video"
        )


def test_invalid_cut_request_is_a_controlled_error(smoke_tmp_path):
    from app.modules.cat_video.errors import InvalidVideoRequest
    from app.modules.cat_video.service import cut_video

    missing_source = smoke_tmp_path / "does_not_exist.mp4"
    output = smoke_tmp_path / "out.mp4"
    try:
        cut_video(missing_source, output, 0, 5)
        assert False, "phải raise InvalidVideoRequest khi source không tồn tại"
    except InvalidVideoRequest:
        pass


def test_app_wires_cat_video_route(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    # session khong ton tai phai tra loi co kiem soat (khong 500)
    resp = client.post(
        "/api/editor/does-not-exist/cut",
        json={"start": 0, "end": 1},
    )
    assert resp.status_code in (400, 404)


def test_module_docs_exist():
    assert (ROOT / "app/modules/cat_video/README_MODULE.md").is_file()
    assert (ROOT / "app/modules/cat_video/MODULE_STATUS.md").is_file()
