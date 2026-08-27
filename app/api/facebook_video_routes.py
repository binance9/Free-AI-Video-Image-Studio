from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.modules.facebook_video import FacebookVideoDownloadError

router = APIRouter(prefix="/api/facebook-video")


class FacebookDownloadRequest(BaseModel):
    url: str


@router.get("/status")
def facebook_status(request: Request):
    downloader = request.app.state.facebook_video_downloader
    return {
        "available": downloader.is_available(),
        "public_only": True,
        "provider": "yt-dlp",
        "message": "Sẵn sàng tải video Facebook công khai" if downloader.is_available() else "Thiếu yt-dlp; mở lại START_VIDEO_FACTORY.bat để tự cài",
    }


@router.post("/jobs")
def start_facebook_download(payload: FacebookDownloadRequest, request: Request):
    try:
        return request.app.state.facebook_video_jobs.start(payload.url)
    except FacebookVideoDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def facebook_download_job(job_id: str, request: Request):
    try:
        return request.app.state.facebook_video_jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy job tải Facebook") from exc


@router.get("/jobs/{job_id}/file")
def facebook_download_file(job_id: str, request: Request):
    try:
        path = request.app.state.facebook_video_jobs.file_path(job_id)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="File Facebook chưa sẵn sàng") from exc
    return FileResponse(path, media_type="video/mp4", filename=Path(path).name)

@router.post("/jobs/{job_id}/cancel")
def cancel_facebook_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.facebook_video_jobs.cancel(job_id)}
