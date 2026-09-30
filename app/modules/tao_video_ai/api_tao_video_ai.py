from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .service import _parse_duration

router = APIRouter(prefix="/api/ai-video", tags=["ai-video-local"])


class TextVideoRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    quality: str = "balanced"
    duration: float = 3.0
    fps: int = 16
    seed: int = 0


def _valid(quality, duration, fps):
    if quality not in {"draft", "balanced", "high"}:
        raise ValueError("quality phải là draft/balanced/high")
    if not (2.0 <= _parse_duration(duration) <= 6.0):
        raise ValueError("duration hỗ trợ 2-6 giây ở bản local đầu tiên")
    if not (8 <= int(fps) <= 24):
        raise ValueError("fps hỗ trợ 8-24")


@router.get("/status")
def status(request: Request):
    return request.app.state.video_ai_service.status()


@router.post("/jobs/text")
def text_to_video(payload: TextVideoRequest, request: Request):
    try:
        _valid(payload.quality, payload.duration, payload.fps)
        jid = request.app.state.video_ai_jobs.start_text(
            prompt=payload.prompt, quality=payload.quality, duration=payload.duration,
            fps=payload.fps, seed=payload.seed,
        )
        return {"job_id": jid, "status_url": f"/api/ai-video/jobs/{jid}"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/image")
def image_to_video(request: Request, file: UploadFile = File(...), prompt: str = Form(""),
                   quality: str = Form("balanced"), duration: float = Form(3.0),
                   fps: int = Form(16), seed: int = Form(0)):
    temp = None
    try:
        _valid(quality, duration, fps)
        suffix = Path(file.filename or "input.png").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Ảnh đầu vào phải là PNG/JPG/WebP")
        with NamedTemporaryFile(delete=False, suffix=suffix) as out:
            shutil.copyfileobj(file.file, out)
            temp = Path(out.name)
        jid = request.app.state.video_ai_jobs.start_image(
            temp, prompt=prompt, quality=quality, duration=duration, fps=fps, seed=seed
        )
        return {"job_id": jid, "status_url": f"/api/ai-video/jobs/{jid}"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp:
            temp.unlink(missing_ok=True)


@router.get("/jobs/{job_id}")
def job(job_id: str, request: Request):
    try:
        return request.app.state.video_ai_jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy job AI video") from exc


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, request: Request):
    return {"cancelled": request.app.state.video_ai_jobs.cancel(job_id)}


@router.get("/media/{filename}")
def media(filename: str, request: Request):
    try:
        path = request.app.state.video_ai_workspace.media_path(filename)
        return FileResponse(path, media_type="video/mp4", filename=path.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy video") from exc
