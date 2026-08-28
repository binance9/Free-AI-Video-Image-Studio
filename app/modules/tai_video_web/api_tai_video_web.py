from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .downloader import WebVideoDownloadError

router = APIRouter(prefix="/api/tai-video-web", tags=["tai-video-web"])


class WebVideoDownloadRequest(BaseModel):
    url: str = Field(min_length=3)
    quality: str = Field(default="best", pattern=r"^(360p|720p|1080p|best)$")
    audio_only: bool = False


@router.get("/status")
def web_video_status(request: Request):
    downloader = request.app.state.tai_video_web_downloader
    available = downloader.is_available()
    return {
        "available": available,
        "provider": "yt-dlp",
        "qualities": ["360p", "720p", "1080p", "best"],
        "message": "Sẵn sàng tải video từ YouTube và các trang phổ biến"
        if available
        else "Thiếu yt-dlp; mở lại START_VIDEO_FACTORY.bat để tự cài",
    }


@router.post("/jobs")
def start_web_video_download(payload: WebVideoDownloadRequest, request: Request):
    try:
        return request.app.state.tai_video_web_jobs.start(
            payload.url, quality=payload.quality, audio_only=payload.audio_only
        )
    except WebVideoDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def web_video_download_job(job_id: str, request: Request):
    try:
        payload = request.app.state.tai_video_web_jobs.get(job_id)
        payload["message"] = payload.get("detail") or payload.get("stage") or ""
        payload["preview_type"] = "video"
        result = payload.get("result") or {}
        session_id = (result.get("editor") or {}).get("session_id")
        payload["preview_url"] = f"/api/editor/{session_id}/media" if session_id else None
        return payload
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy job tải video") from exc


@router.get("/jobs/{job_id}/file")
def web_video_download_file(job_id: str, request: Request):
    try:
        path = request.app.state.tai_video_web_jobs.file_path(job_id)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="File chưa sẵn sàng") from exc
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "video/mp4"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/jobs/{job_id}/cancel")
def cancel_web_video_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.tai_video_web_jobs.cancel(job_id)}
