"""Smoke test cho module lam_sach_video (xoa nen / inpaint AI) - nhanh,
KHONG chay rembg/OpenCV that.

Chay: pytest -q tests/smoke/test_lam_sach_video_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_status(smoke_tmp_path):
    from app.modules.lam_sach_video import VideoCleanupRuntime, VideoCleanupJobManager
    from app.modules.lam_sach_video.api_lam_sach_video import router

    runtime = VideoCleanupRuntime(ROOT, smoke_tmp_path / "runtime", smoke_tmp_path / "models")
    status = runtime.status()
    assert "ready" in status
    assert router.routes
    assert VideoCleanupJobManager is not None


def test_worker_scripts_point_to_own_module_folder():
    """Bug that o phien truoc: runtime.py tung tro toi thu muc module CU
    (video_cleanup) bang string path rieng, khong phai import Python nen
    grep import thuong bo sot."""
    from app.modules.lam_sach_video.runtime import VideoCleanupRuntime
    runtime = VideoCleanupRuntime(ROOT, ROOT / "data" / "runtime_video_cleanup", ROOT / "data" / "models")
    assert "lam_sach_video" in str(runtime.background_worker)
    assert "lam_sach_video" in str(runtime.inpaint_worker)
    assert runtime.background_worker.exists()
    assert runtime.inpaint_worker.exists()


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/lam_sach_video/lam_sach_video.js").is_file()
    assert (ROOT / "app/modules/lam_sach_video/README_MODULE.md").is_file()
