"""HTTP endpoints cho do_vat_3d - convention giong het app.modules.nhan_vat_3d
(prefix /api/..., FileResponse cho model/view, job dang {job_id, status_url})."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .cau_hinh_do_vat import QUALITY_MAC_DINH, TEXTURE_MAC_DINH, danh_sach_danh_muc
from .hop_dong_asset import liet_ke_thu_vien
from .phan_loai_do_vat import validate_category, validate_quality, validate_texture

router = APIRouter(prefix="/api/do-vat-3d", tags=["do-vat-3d"])


class PromptDoVat3DRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    category: str = "tu_do"
    quality: str = QUALITY_MAC_DINH
    texture: str = TEXTURE_MAC_DINH
    display_name: str | None = None
    low_vram: bool = False


@router.get("/status")
def status(request: Request):
    return request.app.state.do_vat_3d_service.status()


@router.get("/categories")
def categories():
    return {"items": danh_sach_danh_muc()}


@router.post("/create")
def create_from_image(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("tu_do"),
    quality: str = Form(QUALITY_MAC_DINH),
    texture: str = Form(TEXTURE_MAC_DINH),
    display_name: str = Form(""),
    low_vram: bool = Form(False),
):
    suffix = Path(file.filename or "image.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Ảnh phải là PNG/JPG/WebP")
    try:
        validate_category(category)
        validate_quality(quality)
        validate_texture(texture)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    incoming = request.app.state.do_vat_3d_workspace.root / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / (next(tempfile._get_candidate_names()) + suffix)
    try:
        with tmp.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
        job_id = request.app.state.do_vat_3d_jobs.start(
            category=category, quality=quality, texture_preset=texture,
            image_path=tmp, display_name=display_name or None, low_vram=low_vram,
        )
        return {"job_id": job_id, "status_url": f"/api/do-vat-3d/job/{job_id}"}
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/create-from-prompt")
def create_from_prompt(payload: PromptDoVat3DRequest, request: Request):
    try:
        validate_category(payload.category)
        validate_quality(payload.quality)
        validate_texture(payload.texture)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job_id = request.app.state.do_vat_3d_jobs.start(
        category=payload.category, quality=payload.quality, texture_preset=payload.texture,
        prompt=payload.prompt, display_name=payload.display_name, low_vram=payload.low_vram,
    )
    return {"job_id": job_id, "status_url": f"/api/do-vat-3d/job/{job_id}"}


@router.get("/job/{job_id}")
def job_status(job_id: str, request: Request):
    try:
        payload = request.app.state.do_vat_3d_jobs.get(job_id)
        result = payload.get("result")
        if result:
            result = dict(result)
            result["model_url"] = f"/api/do-vat-3d/output/{result['asset_id']}"
            result["viewer_url"] = f"/api/do-vat-3d/view/{result['asset_id']}"
            payload["result"] = result
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/job/{job_id}/cancel")
def cancel_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.do_vat_3d_jobs.cancel(job_id)}


@router.get("/view/{asset_id}")
def view_glb(asset_id: str, request: Request):
    """Serve GLB inline cho viewer dung chung (window.AIVF3DViewer.show)."""
    try:
        path = request.app.state.do_vat_3d_workspace.model_path(asset_id)
        return FileResponse(path, media_type="model/gltf-binary")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/output/{asset_id}")
def download_glb(asset_id: str, request: Request):
    try:
        path = request.app.state.do_vat_3d_workspace.model_path(asset_id)
        meta = request.app.state.do_vat_3d_workspace.metadata(asset_id)
        filename = meta.get("suggested_filename") or f"do_vat_{asset_id[:8]}.glb"
        return FileResponse(path, filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/assets")
def list_assets(request: Request):
    items = liet_ke_thu_vien(request.app.state.do_vat_3d_workspace.root)
    return {"items": items}
