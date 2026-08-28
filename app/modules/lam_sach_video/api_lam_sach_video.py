from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/cleanup", tags=["video-cleanup"])


class BackgroundCleanupRequest(BaseModel):
    mode: str = Field(default="transparent", pattern=r"^(transparent|solid)$")
    color: str = Field(default="#00ff00", pattern=r"^#[0-9A-Fa-f]{6}$")
    model: str = Field(default="u2net_human_seg", pattern=r"^(u2net_human_seg|isnet-general-use)$")


class OverlayCleanupRequest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    padding: int = Field(default=4, ge=0, le=80)
    method: str = Field(default="delogo", pattern=r"^(delogo|inpaint)$")
    feather: int = Field(default=6, ge=0, le=10)


@router.get("/status")
def cleanup_status(request: Request):
    return request.app.state.video_cleanup_runtime.status()


@router.post("/background/{session_id}")
def cleanup_background(session_id: str, payload: BackgroundCleanupRequest, request: Request):
    try:
        job_id = request.app.state.video_cleanup_jobs.start_background(
            session_id, mode=payload.mode, color=payload.color, model=payload.model
        )
        return {"job_id": job_id, "status_url": f"/api/cleanup/jobs/{job_id}"}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/overlay/{session_id}")
def cleanup_overlay(session_id: str, payload: OverlayCleanupRequest, request: Request):
    try:
        job_id = request.app.state.video_cleanup_jobs.start_overlay(
            session_id, x=payload.x, y=payload.y, w=payload.w, h=payload.h,
            padding=payload.padding, method=payload.method, feather=payload.feather,
        )
        return {"job_id": job_id, "status_url": f"/api/cleanup/jobs/{job_id}"}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/preview/{session_id}")
def cleanup_preview(session_id: str, payload: OverlayCleanupRequest, request: Request):
    """Xem truoc THAT ngay lap tuc (1 frame giua video): anh goc -> mask ->
    da inpaint -> final (blend mep + sharpen nhe). Dung de kiem tra vung xoa
    truoc khi chay toan bo video."""
    try:
        return request.app.state.video_cleanup_jobs.preview_overlay(
            session_id, x=payload.x, y=payload.y, w=payload.w, h=payload.h,
            padding=payload.padding, feather=payload.feather,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def cleanup_job(job_id: str, request: Request):
    try:
        payload=request.app.state.video_cleanup_jobs.get(job_id)
        payload["message"]=payload.get("detail") or payload.get("stage") or ""
        payload["preview_type"]="video"
        editor=(payload.get("result") or {}).get("editor") or {}
        session_id=editor.get("session_id")
        payload["preview_url"]=f"/api/editor/{session_id}/media" if session_id else None
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/jobs/{job_id}/cancel")
def cancel_cleanup_job(job_id: str, request: Request):
    return {"cancelled": request.app.state.video_cleanup_jobs.cancel(job_id)}
