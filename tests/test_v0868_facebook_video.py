from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.modules.tai_video.downloader import FacebookVideoDownloader, FacebookVideoDownloadError
from app.modules.tai_video.job_manager import FacebookVideoJobManager

ROOT = Path(__file__).resolve().parents[1]


def test_facebook_module_is_separate_and_visible():
    cfg = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/facebook_video.js").read_text(encoding="utf-8")
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'version: str = "0.8.9.0"' in cfg
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in html
    assert 'TẢI VIDEO TỪ FACEBOOK' in html
    assert ('data-tool="facebook"' in html) or ('data-tool-open="facebook"' in html)
    assert '/api/facebook-video/jobs' in js
    assert 'yt-dlp' in req
    assert 'facebook_video_router' in main


def test_only_facebook_public_link_shapes_are_accepted(tmp_path):
    downloader = FacebookVideoDownloader(tmp_path / "library")
    assert downloader.validate_url("https://www.facebook.com/user/videos/123")
    assert downloader.validate_url("https://fb.watch/abc123/")
    assert downloader.validate_url("https://m.facebook.com/reel/123")
    with pytest.raises(FacebookVideoDownloadError):
        downloader.validate_url("https://example.com/video.mp4")
    with pytest.raises(FacebookVideoDownloadError):
        downloader.validate_url("file:///tmp/video.mp4")


def test_job_imports_downloaded_video_into_editor(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake-video-content")

    class FakeDownloader:
        def validate_url(self, url):
            return url
        def download(self, url, job_dir, progress):
            progress(50, "Đang tải video từ Facebook", "1 / 2 MB")
            out = tmp_path / "library.mp4"
            out.write_bytes(source.read_bytes())
            return {"path": str(out), "title": "Facebook Test", "video_id": "123", "uploader": "Tester", "size_bytes": out.stat().st_size}

    class FakeWorkspace:
        def __init__(self):
            self.root = tmp_path / "sessions"
            self.root.mkdir()
            self.received = None
        def create(self, incoming, original_name):
            self.received = (Path(incoming), original_name)
            assert Path(incoming).is_file()
            return {"session_id": "a" * 32, "original_name": original_name, "duration": 1, "width": 1, "height": 1, "fps": 1, "can_undo": False}

    workspace = FakeWorkspace()
    jobs = FacebookVideoJobManager(FakeDownloader(), workspace, tmp_path / "jobs")
    job = jobs.start("https://facebook.com/test/videos/123")
    for _ in range(100):
        current = jobs.get(job["job_id"])
        if current["status"] in {"done", "error"}:
            break
        time.sleep(0.01)
    assert current["status"] == "done", current
    assert current["progress"] == 100
    assert current["result"]["editor"]["session_id"] == "a" * 32
    assert workspace.received is not None
