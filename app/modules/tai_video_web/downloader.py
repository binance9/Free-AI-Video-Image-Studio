"""Generic web video downloader via yt-dlp - YouTube va cac trang pho bien
(khong gioi han rieng Facebook, xem app.modules.tai_video cho Facebook).

Ho tro:
- chon chat luong 360p / 720p / 1080p / best
- tai video HOAC chi audio
- neu yt-dlp tra ve video/audio tach stream (thuong xay ra voi cac dinh
  dang HD tren YouTube), yt-dlp tu goi FFmpeg de ghep lai (merge_output_format)
- luu file vao thu muc output rieng cua module nay (khong dung chung voi
  thu vien Facebook)
"""
from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin, run_tool
from app.modules.chinh_sua_video.errors import VideoEditorError
from app.core.shared_services import JobCancelled

ProgressCallback = Callable[[int, str, str], None]

QUALITY_FORMATS: dict[str, str] = {
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "best": "bestvideo+bestaudio/best",
}

_SAFE_TITLE = re.compile(r"[^A-Za-z0-9._-]+")


class WebVideoDownloadError(RuntimeError):
    """Raised when a generic web video download cannot be completed."""


class WebVideoDownloader:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("yt_dlp") is not None

    @staticmethod
    def validate_url(url: str) -> str:
        raw = (url or "").strip()
        try:
            parsed = urlparse(raw)
        except ValueError as exc:
            raise WebVideoDownloadError("URL không hợp lệ") from exc
        if parsed.scheme not in {"http", "https"}:
            raise WebVideoDownloadError("URL phải bắt đầu bằng http:// hoặc https://")
        if not parsed.hostname:
            raise WebVideoDownloadError("URL không có tên miền hợp lệ")
        return raw

    def download(
        self,
        url: str,
        job_dir: str | Path,
        *,
        quality: str = "best",
        audio_only: bool = False,
        progress: ProgressCallback | None = None,
        cancel_event=None,
    ) -> dict:
        safe_url = self.validate_url(url)
        if not self.is_available():
            raise WebVideoDownloadError(
                "Thiếu yt-dlp. Đóng app rồi mở START_VIDEO_FACTORY.bat để Studio tự cài module tải video."
            )
        if quality not in QUALITY_FORMATS:
            raise WebVideoDownloadError("Chất lượng phải là 360p, 720p, 1080p hoặc best")
        import yt_dlp  # imported lazily so the editor can still boot without it

        job_path = Path(job_dir).resolve()
        job_path.mkdir(parents=True, exist_ok=True)

        def report(pct: int, stage: str, detail: str) -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled("Đã dừng tải video")
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
                report(pct, "Đang tải video", detail)
            elif status == "finished":
                report(
                    90, "Đã tải xong",
                    "Đang trích xuất audio bằng FFmpeg…" if audio_only else "Đang ghép luồng video/âm thanh bằng FFmpeg…",
                )

        opts: dict = {
            "outtmpl": str(job_path / "web_%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 25,
            "windowsfilenames": True,
            "restrictfilenames": True,
            "progress_hooks": [hook],
            "ffmpeg_location": ffmpeg_bin(),
        }
        if audio_only:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        else:
            opts["format"] = QUALITY_FORMATS[quality]
            opts["merge_output_format"] = "mp4"  # yt-dlp+FFmpeg tu ghep video/audio tach stream

        report(5, "Kiểm tra URL", "Đang phân tích trang nguồn qua yt-dlp…")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(safe_url, download=True)
        except JobCancelled:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise WebVideoDownloadError(f"Không tải được video: {message}") from exc

        wanted_suffixes = {".mp3"} if audio_only else {".mp4", ".m4v", ".mov", ".mkv", ".webm"}
        candidates = [
            p for p in job_path.iterdir() if p.is_file() and p.suffix.lower() in wanted_suffixes
        ]
        if not candidates:
            raise WebVideoDownloadError("yt-dlp chạy xong nhưng không tìm thấy file kết quả")
        source = max(candidates, key=lambda p: p.stat().st_mtime)
        if source.stat().st_size < 1024:
            raise WebVideoDownloadError("File tải về không hợp lệ")

        if not audio_only and source.suffix.lower() != ".mp4":
            # yt-dlp merge doi khi ra .mkv/.webm neu codec khong tuong thich mp4 truc tiep.
            report(92, "Chuẩn hóa MP4", "Đang remux video để editor mở ổn định…")
            mp4_path = job_path / "web_final.mp4"
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
        title = str(info.get("title") or f"Video {video_id}").strip()
        safe_id = _SAFE_TITLE.sub("_", video_id).strip("._")[:80] or "video"
        suffix = source.suffix.lower()
        output_path = self.output_dir / f"web_{safe_id}{suffix}"
        if output_path.exists():
            output_path = self.output_dir / f"web_{safe_id}_{source.stat().st_size}{suffix}"
        shutil.copy2(source, output_path)
        report(94, "Đưa video vào AI Video Factory", title[:100])
        return {
            "path": str(output_path),
            "title": title,
            "video_id": video_id,
            "uploader": str(info.get("uploader") or ""),
            "duration": info.get("duration"),
            "source_url": safe_url,
            "size_bytes": output_path.stat().st_size,
            "audio_only": audio_only,
            "quality": quality,
        }
