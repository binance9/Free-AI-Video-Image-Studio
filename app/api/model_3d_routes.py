"""HTTP endpoints for free local image/prompt to 3D generation."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/3d", tags=["3d-local"])


class Prompt3DRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    style: str = "cartoon3d"
    resolution: int = Field(default=256, ge=128, le=512)
    texture: bool = False
    preview: bool = True
    backend: str = "quick"
    optimize_mesh: bool = True
    mesh_profile: str = Field(default="hd", pattern=r"^(hd|medium|light)$")


def _save_result(request: Request, result: dict, meta: dict) -> dict:
    payload = request.app.state.model_3d_workspace.create_asset(
        result["model_path"], result.get("preview_path"), meta
    )
    payload["model_url"] = f"/api/3d/model/{payload['asset_id']}"
    payload["preview_url"] = f"/api/3d/preview/{payload['asset_id']}" if payload.get("preview") else None
    return payload


@router.get("/status")
def status(request: Request):
    return request.app.state.model_3d_service.status()


@router.post("/from-image")
def from_image(request: Request, file: UploadFile = File(...), resolution: int = Form(256),
               texture: bool = Form(False), preview: bool = Form(True), backend: str = Form("quick"),
               optimize_mesh: bool = Form(True), mesh_profile: str = Form("hd")):
    suffix = Path(file.filename or "image.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Ảnh phải là PNG/JPG/WebP")
    with tempfile.TemporaryDirectory(prefix="aivf3d_") as td:
        src = Path(td) / ("input" + suffix)
        try:
            with src.open("wb") as out:
                shutil.copyfileobj(file.file, out, length=1024 * 1024)
            result = request.app.state.model_3d_service.from_image(
                src, Path(td) / "out", resolution=resolution, texture=texture, render_preview=preview, backend=backend, optimize_mesh=optimize_mesh, mesh_profile=mesh_profile
            )
            return _save_result(request, result, {
                "source": "image", "resolution": resolution, "texture": bool(result.get("texture_applied", texture)), "backend": result.get("backend", backend), "quality_backend": backend,
                "mesh_optimized": bool(result.get("mesh_optimized", False)), "faces_before": result.get("faces_before"), "faces_after": result.get("faces_after"), "mesh_profile": result.get("mesh_profile", mesh_profile if optimize_mesh else "original")
            })
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/from-prompt")
def from_prompt(payload: Prompt3DRequest, request: Request):
    with tempfile.TemporaryDirectory(prefix="aivf3dprompt_") as td:
        try:
            result = request.app.state.model_3d_service.from_prompt(
                payload.prompt, Path(td), style=payload.style, resolution=payload.resolution,
                texture=payload.texture, render_preview=payload.preview, backend=payload.backend, optimize_mesh=payload.optimize_mesh, mesh_profile=payload.mesh_profile,
            )
            response = _save_result(request, result, {
                "source": "prompt", "prompt": payload.prompt, "style": payload.style,
                "resolution": payload.resolution, "texture": bool(result.get("texture_applied", payload.texture)), "backend": result.get("backend", payload.backend), "quality_backend": payload.backend,
                "mesh_optimized": bool(result.get("mesh_optimized", False)), "faces_before": result.get("faces_before"), "faces_after": result.get("faces_after"), "mesh_profile": result.get("mesh_profile", payload.mesh_profile if payload.optimize_mesh else "original")
            })
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc



@router.post("/jobs/from-image")
def start_image_job(request: Request, file: UploadFile = File(...), resolution: int = Form(256),
                    texture: bool = Form(False), preview: bool = Form(False), backend: str = Form("quick"),
                    optimize_mesh: bool = Form(True), mesh_profile: str = Form("hd")):
    suffix = Path(file.filename or "image.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Ảnh phải là PNG/JPG/WebP")
    incoming = request.app.state.model_3d_workspace.root / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / (next(tempfile._get_candidate_names()) + suffix)
    try:
        with tmp.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
        job_id = request.app.state.model_3d_jobs.start_image(
            tmp, resolution=resolution, texture=texture, preview=preview, backend=backend, optimize_mesh=optimize_mesh, mesh_profile=mesh_profile
        )
        return {"job_id": job_id, "status_url": f"/api/3d/jobs/{job_id}"}
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/jobs/from-prompt")
def start_prompt_job(payload: Prompt3DRequest, request: Request):
    job_id = request.app.state.model_3d_jobs.start_prompt(
        payload.prompt, style=payload.style, resolution=payload.resolution,
        texture=payload.texture, preview=False, backend=payload.backend, optimize_mesh=payload.optimize_mesh, mesh_profile=payload.mesh_profile,
    )
    return {"job_id": job_id, "status_url": f"/api/3d/jobs/{job_id}"}


@router.post("/jobs/colorize")
def start_colorize_job(request: Request, image: UploadFile = File(...), asset_id: str = Form(""),
                       model: UploadFile | None = File(None)):
    image_suffix = Path(image.filename or "reference.png").suffix.lower() or ".png"
    if image_suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Ảnh tham chiếu phải là PNG/JPG/WebP")
    incoming = request.app.state.model_3d_workspace.root / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    ref_path = incoming / (next(tempfile._get_candidate_names()) + image_suffix)
    mesh_tmp = None
    try:
        with ref_path.open("wb") as out:
            shutil.copyfileobj(image.file, out, length=1024 * 1024)
        if model is not None and model.filename:
            mesh_suffix = Path(model.filename).suffix.lower()
            if mesh_suffix != ".glb":
                raise HTTPException(status_code=400, detail="Model để tô màu phải là GLB")
            mesh_tmp = incoming / (next(tempfile._get_candidate_names()) + ".glb")
            with mesh_tmp.open("wb") as out:
                shutil.copyfileobj(model.file, out, length=1024 * 1024)
            mesh_path = mesh_tmp
        elif asset_id:
            try:
                mesh_path = request.app.state.model_3d_workspace.model_path(asset_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        else:
            raise HTTPException(status_code=400, detail="Chọn GLB hoặc dùng model vừa tạo trước khi tô màu")
        job_id = request.app.state.model_3d_jobs.start_colorize(mesh_path, ref_path)
        return {"job_id": job_id, "status_url": f"/api/3d/jobs/{job_id}"}
    finally:
        ref_path.unlink(missing_ok=True)
        if mesh_tmp is not None:
            mesh_tmp.unlink(missing_ok=True)


@router.get("/jobs/{job_id}")
def job_status(job_id: str, request: Request):
    try:
        payload = request.app.state.model_3d_jobs.get(job_id)
        result = payload.get("result")
        if result:
            result = dict(result)
            result["model_url"] = f"/api/3d/model/{result['asset_id']}"
            result["viewer_url"] = f"/api/3d/view/{result['asset_id']}"
            result["preview_url"] = f"/api/3d/preview/{result['asset_id']}" if result.get("preview") else None
            payload["result"] = result
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/view/{asset_id}")
def model_view(asset_id: str, request: Request):
    """Serve GLB inline for the local interactive viewer."""
    try:
        path = request.app.state.model_3d_workspace.model_path(asset_id)
        return FileResponse(path, media_type="model/gltf-binary")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/model/{asset_id}")
def model_file(asset_id: str, request: Request):
    try:
        path = request.app.state.model_3d_workspace.model_path(asset_id)
        return FileResponse(path, filename=f"AI_Video_Factory_{asset_id[:8]}{path.suffix}")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/preview/{asset_id}")
def preview_file(asset_id: str, request: Request):
    try:
        path = request.app.state.model_3d_workspace.preview_path(asset_id)
        return FileResponse(path, media_type="video/mp4")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/turntable")
def export_turntable(request: Request, video: UploadFile = File(...), ratio: str = Form("1:1"), duration: int = Form(8)):
    """Convert a local viewer capture to a share-ready H.264 MP4."""
    if ratio not in {"1:1", "16:9"}:
        raise HTTPException(status_code=400, detail="Tỷ lệ phải là 1:1 hoặc 16:9")
    duration = 12 if int(duration) >= 12 else 8
    incoming = request.app.state.model_3d_workspace.root / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / (next(tempfile._get_candidate_names()) + ".webm")
    try:
        with tmp.open("wb") as out:
            shutil.copyfileobj(video.file, out, length=1024 * 1024)
        path = request.app.state.model_3d_turntable.export(tmp, ratio=ratio, duration=duration)
        return FileResponse(path, media_type="video/mp4", filename=path.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Xuất video xoay 3D lỗi: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.model_3d_jobs.cancel(job_id)}
