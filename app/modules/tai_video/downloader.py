"""Download public Facebook videos with yt-dlp into the local studio.

This module deliberately does not use browser cookies, credentials, or private-session
bypass. It is for public Facebook links the user is allowed to download.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from app.modules.chinh_sua_video.ffmpeg_tools import run_tool
from app.modules.chinh_sua_video.errors import VideoEditorError
from app.modules.job_control import JobCancelled


ProgressCallback = Callable[[int, str, str], None]


class FacebookVideoDownloadError(RuntimeError):
    """Raised when a Facebook import cannot be completed."""


_ALLOWED_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com", "fb.watch", "www.fb.watch"}
_SAFE_TITLE = re.compile(r"[^A-Za-z0-9._-]+")


class FacebookVideoDownloader:
    def __init__(self, library_dir: str | Path):
        self.library_dir = Path(library_dir).resolve()
        self.library_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("yt_dlp") is not None

    @staticmethod
    def validate_url(url: str) -> str:
        raw = (url or "").strip()
        try:
            parsed = urlparse(raw)
        except ValueError as exc:
            raise FacebookVideoDownloadError("Link Facebook không hợp lệ") from exc
        if parsed.scheme not in {"http", "https"}:
            raise FacebookVideoDownloadError("Link phải bắt đầu bằng http:// hoặc https://")
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed = host in _ALLOWED_HOSTS or host.endswith(".facebook.com")
        if not allowed:
            raise FacebookVideoDownloadError("Chỉ hỗ trợ link video Facebook / fb.watch")
        if not parsed.path or parsed.path == "/":
            raise FacebookVideoDownloadError("Hãy dán link trực tiếp tới video / reel Facebook")
        return raw

    def download(self, url: str, job_dir: str | Path, progress: ProgressCallback | None = None, cancel_event=None) -> dict:
        safe_url = self.validate_url(url)
        if not self.is_available():
            raise FacebookVideoDownloadError(
                "Thiếu yt-dlp. Đóng app rồi mở START_VIDEO_FACTORY.bat để Studio tự cài module tải Facebook."
            )
        import yt_dlp  # imported lazily so the editor can still boot without it

        job_path = Path(job_dir).resolve()
        job_path.mkdir(parents=True, exist_ok=True)

        def report(pct: int, stage: str, detail: str) -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled("Đã dừng tải Facebook")
            if progress:
                progress(max(0, min(100, int(pct))), stage, detail)

        def hook(data: dict) -> None:
            status = data.get("status")
            if status == "downloading":
                downloaded = int(data.get("downloaded_bytes") or 0)
                total = int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
                if total > 0:
                    ratio = min(1.0, downloaded / total)
                    pct = 8 + int(ratio * 78)
                    detail = f"{downloaded / 1048576:.1f} / {total / 1048576:.1f} MB"
                else:
                    pct = 18
                    detail = f"Đã tải {downloaded / 1048576:.1f} MB"
                speed = data.get("speed")
                if speed:
                    detail += f" · {float(speed) / 1048576:.1f} MB/s"
                report(pct, "Đang tải video từ Facebook", detail)
            elif status == "finished":
                report(90, "Đã tải xong", "Đang ghép luồng video / âm thanh bằng FFmpeg…")

        opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
            "outtmpl": str(job_path / "facebook_%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 25,
            "windowsfilenames": True,
            "restrictfilenames": True,
            "progress_hooks": [hook],
        }
        report(5, "Kiểm tra link Facebook", "Chỉ tải video công khai, không dùng cookie đăng nhập")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(safe_url, download=True)
        except JobCancelled:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            if "login" in message.lower() or "cookie" in message.lower() or "private" in message.lower():
                raise FacebookVideoDownloadError(
                    "Facebook yêu cầu đăng nhập hoặc video không công khai. Module này chỉ tải video công khai."
                ) from exc
            raise FacebookVideoDownloadError(f"Không tải được video Facebook: {message}") from exc

        candidates = [
            p for p in job_path.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv", ".webm"}
        ]
        if not candidates:
            raise FacebookVideoDownloadError("yt-dlp chạy xong nhưng không tìm thấy file video")
        source = max(candidates, key=lambda p: p.stat().st_mtime)
        if source.stat().st_size < 1024:
            raise FacebookVideoDownloadError("File Facebook tải về không hợp lệ")

        if source.suffix.lower() != ".mp4":
            report(92, "Chuẩn hóa MP4", "Đang remux video để editor mở ổn định…")
            mp4_path = job_path / "facebook_final.mp4"
            try:
                run_tool([
                    "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
                    "-c", "copy", "-movflags", "+faststart", str(mp4_path),
                ])
            except VideoEditorError:
                report(92, "Chuẩn hóa MP4", "Codec nguồn không remux được; đang chuyển mã tương thích…")
                run_tool([
                    "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4_path),
                ])
            source = mp4_path

        video_id = str(info.get("id") or "video")
        title = str(info.get("title") or f"Facebook {video_id}").strip()
        safe_id = _SAFE_TITLE.sub("_", video_id).strip("._")[:80] or "video"
        suffix = source.suffix.lower()
        library_path = self.library_dir / f"facebook_{safe_id}{suffix}"
        if library_path.exists():
            library_path = self.library_dir / f"facebook_{safe_id}_{source.stat().st_size}{suffix}"
        shutil.copy2(source, library_path)
        report(94, "Đưa video vào AI Video Factory", title[:100])
        return {
            "path": str(library_path),
            "title": title,
            "video_id": video_id,
            "uploader": str(info.get("uploader") or ""),
            "duration": info.get("duration"),
            "source_url": safe_url,
            "size_bytes": library_path.stat().st_size,
        }
