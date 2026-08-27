"""Free local AI image generation/editing and editor import endpoints."""
from __future__ import annotations

import shutil
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["ai-image-local"])

_ALLOWED_SIZE = {"1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840"}
_ALLOWED_QUALITY = {"medium", "high"}
_ALLOWED_STYLE = {"photo", "cartoon3d", "anime", "cinematic", "illustration", "product", "fantasy"}


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=3000)
    style: str = "photo"
    size: str = "1536x1024"
    quality: str = "high"


def _validate(style: str, size: str, quality: str):
    if style not in _ALLOWED_STYLE or size not in _ALLOWED_SIZE or quality not in _ALLOWED_QUALITY:
        raise ValueError("Tùy chọn AI ảnh không hợp lệ")


@router.post("/ai-image/generate")
def generate_image(payload: GenerateRequest, request: Request):
    try:
        _validate(payload.style, payload.size, payload.quality)
        data = request.app.state.ai_image_service.generate(payload.prompt, payload.style, payload.size, payload.quality)
        return request.app.state.ai_image_workspace.save(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ai-image/edit")
def edit_image(request: Request, file: UploadFile = File(...), prompt: str = Form(...), style: str = Form("photo"), size: str = Form("1536x1024"), quality: str = Form("high")):
    temp_path = None
    try:
        _validate(style, size, quality)
        suffix = ".png" if not file.filename else ("." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".png")
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Ảnh tham chiếu phải là PNG, JPG hoặc WebP")
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=request.app.state.ai_image_workspace.root) as target:
            shutil.copyfileobj(file.file, target, length=1024 * 1024)
            temp_path = target.name
        data = request.app.state.ai_image_service.edit(temp_path, prompt, style, size, quality)
        return request.app.state.ai_image_workspace.save(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path:
            from pathlib import Path
            Path(temp_path).unlink(missing_ok=True)


@router.get("/ai-image/{image_id}")
def ai_image_media(image_id: str, request: Request):
    try:
        return FileResponse(request.app.state.ai_image_workspace.path(image_id), media_type="image/png")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/editor/{session_id}/asset-from-ai/{image_id}")
def import_ai_image(session_id: str, image_id: str, request: Request):
    try:
        path = request.app.state.ai_image_workspace.path(image_id)
        return request.app.state.video_workspace.import_ai_image(session_id, path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/ai-image/jobs/generate")
def start_generate_image_job(payload: GenerateRequest, request: Request):
    try:
        _validate(payload.style, payload.size, payload.quality)
        job_id = request.app.state.ai_image_jobs.start_generate(
            prompt=payload.prompt, style=payload.style, size=payload.size, quality=payload.quality
        )
        return {"job_id": job_id, "status_url": f"/api/ai-image/jobs/{job_id}"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ai-image/jobs/edit")
def start_edit_image_job(request: Request, file: UploadFile = File(...), prompt: str = Form(...),
                         style: str = Form("photo"), size: str = Form("1536x1024"), quality: str = Form("high")):
    temp_path = None
    try:
        _validate(style, size, quality)
        suffix = ".png" if not file.filename else ("." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".png")
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Ảnh tham chiếu phải là PNG, JPG hoặc WebP")
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=request.app.state.ai_image_workspace.root) as target:
            shutil.copyfileobj(file.file, target, length=1024 * 1024)
            temp_path = target.name
        job_id = request.app.state.ai_image_jobs.start_edit(
            temp_path, prompt=prompt, style=style, size=size, quality=quality
        )
        return {"job_id": job_id, "status_url": f"/api/ai-image/jobs/{job_id}"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path:
            from pathlib import Path
            Path(temp_path).unlink(missing_ok=True)


@router.get("/ai-image/jobs/{job_id}")
def ai_image_job(job_id: str, request: Request):
    try:
        return request.app.state.ai_image_jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy job AI ảnh") from exc


@router.post("/ai-image/jobs/{job_id}/cancel")
def cancel_ai_image_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.ai_image_jobs.cancel(job_id)}
