from __future__ import annotations

import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from io import BytesIO
from uuid import uuid4
from PIL import Image
from pydantic import BaseModel, Field

from .service import AIVideoDirectorService
from .auto_producer import AutoProduceJobManager

router = APIRouter(prefix="/api/ai-video-director", tags=["ai-video-director"])


class PlanRequest(BaseModel):
    idea: str = Field(min_length=3, max_length=4000)
    duration_seconds: int = Field(default=30, ge=5, le=600)
    platform: str = "TikTok/Reels"
    aspect_ratio: str | None = None
    style: str = "cinematic, polished, modern"
    audience: str = "người xem phổ thông"
    goal: str = "thu hút người xem và truyền tải ý chính rõ ràng"
    voice_style: str = "tự nhiên, rõ, có nhịp"
    music_mood: str = "cinematic phù hợp nội dung"
    captions: bool = True
    character_lock: bool = True
    quality_priority: str = "quality_first"
    project_id: str | None = None


class PatchRequest(BaseModel):
    plan: dict
    scene_id: int
    instruction: str = Field(min_length=1, max_length=2000)


class SaveRequest(BaseModel):
    plan: dict


class ProduceRequest(BaseModel):
    plan: dict
    quality: str = "balanced"
    fast_mode: bool = False



class ProjectMemoryRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=120)
    memory: dict


class FeedbackMemoryRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    project_id: str | None = None
    scope: str = "video"
    kind: str = "preference"


class RouteTaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    requested_output: str | None = None
    explicit_module: str | None = None


def _base(request: Request) -> Path:
    model_dir = Path(getattr(request.app.state, "model_dir", Path.cwd() / "models"))
    return model_dir.parent if model_dir.name == "models" else Path.cwd()


def _svc(request: Request) -> AIVideoDirectorService:
    svc = getattr(request.app.state, "ai_video_director_service", None)
    if svc is None:
        svc = AIVideoDirectorService(_base(request) / "data" / "ai_video_director")
        request.app.state.ai_video_director_service = svc
    return svc


def _producer_jobs(request: Request) -> AutoProduceJobManager:
    jobs = getattr(request.app.state, "ai_video_director_produce_jobs", None)
    if jobs is None:
        jobs = AutoProduceJobManager(request.app, _base(request) / "data" / "ai_video_director" / "productions")
        request.app.state.ai_video_director_produce_jobs = jobs
    return jobs




def _references_dir(request: Request) -> Path:
    d = _base(request) / "data" / "ai_video_director" / "references"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/reference")
@router.post("/character-reference")
async def upload_reference(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Reference phải là file ảnh")
    data = await request.body()
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh tham chiếu rỗng hoặc lớn hơn 20MB")
    try:
        im = Image.open(BytesIO(data)).convert("RGB")
        if im.width < 128 or im.height < 128:
            raise ValueError("Ảnh quá nhỏ")
        rid = uuid4().hex
        out = _references_dir(request) / f"{rid}.png"
        im.save(out, format="PNG", optimize=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ảnh tham chiếu không hợp lệ: {exc}")
    return {"ok": True, "reference_id": rid, "width": im.width, "height": im.height, "preview_url": f"/api/ai-video-director/reference/{rid}"}


@router.get("/reference/{reference_id}")
@router.get("/character-reference/{reference_id}")
def get_reference(reference_id: str, request: Request):
    if not reference_id.isalnum() or len(reference_id) > 64:
        raise HTTPException(status_code=400, detail="reference_id không hợp lệ")
    path = _references_dir(request) / f"{reference_id}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh tham chiếu")
    return FileResponse(path, media_type="image/png", filename="character_reference.png")


@router.delete("/reference/{reference_id}")
@router.delete("/character-reference/{reference_id}")
def delete_reference(reference_id: str, request: Request):
    if not reference_id.isalnum() or len(reference_id) > 64:
        raise HTTPException(status_code=400, detail="reference_id không hợp lệ")
    path = _references_dir(request) / f"{reference_id}.png"
    existed = path.is_file()
    if existed:
        path.unlink()
    return {"ok": True, "deleted": existed}

@router.get("/status")
def status(request: Request):
    info = _svc(request).status()
    info["auto_produce"] = {
        "ready": all(hasattr(request.app.state, x) for x in ("ai_image_service", "video_ai_service")),
        "image_module": hasattr(request.app.state, "ai_image_service"),
        "video_module": hasattr(request.app.state, "video_ai_service"),
        "music_module": hasattr(request.app.state, "music_library"),
        "voice_backend": "Windows SAPI local when available",
        "caption_backend": "Director SRT timeline",
        "quality_first": True,
        "character_lock": True,
        "character_reference_api": True,
        "character_reference_routes": ["/api/ai-video-director/reference", "/api/ai-video-director/character-reference"],
        "quality_modes": ["draft", "balanced", "high", "final"],
    }
    return info


@router.post("/route-task")
def route_task_endpoint(body: RouteTaskRequest, request: Request):
    try:
        return {"ok": True, "route": _svc(request).route_module_task(body.text, body.requested_output, body.explicit_module)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))




@router.get("/memory/status")
def memory_status(request: Request):
    return {"ok": True, "memory": _svc(request).memory.status()}


@router.get("/memory/context")
def memory_context(request: Request, project_id: str | None = None):
    return {"ok": True, "context": _svc(request).memory_context(project_id=project_id)}


@router.post("/memory/project")
def memory_project(body: ProjectMemoryRequest, request: Request):
    try:
        return {"ok": True, "project_id": body.project_id, "memory": _svc(request).update_project_memory(body.project_id, body.memory)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/memory/feedback")
def memory_feedback(body: FeedbackMemoryRequest, request: Request):
    try:
        item = _svc(request).remember_feedback(body.text, body.project_id, body.scope, body.kind)
        return {"ok": True, "feedback": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/plan")
def create_plan(body: PlanRequest, request: Request):
    try:
        return {"ok": True, "plan": _svc(request).build_plan(body.model_dump())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/patch-scene")
def patch_scene(body: PatchRequest, request: Request):
    try:
        return {"ok": True, "plan": _svc(request).patch_scene(body.plan, body.scene_id, body.instruction)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/save")
def save(body: SaveRequest, request: Request):
    try:
        path = _svc(request).save_project(body.plan)
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/produce")
def produce(body: ProduceRequest, request: Request):
    if body.quality not in {"draft", "balanced", "high", "final"}:
        raise HTTPException(status_code=400, detail="quality phải là draft/balanced/high/final")
    if not isinstance(body.plan.get("scenes"), list) or not body.plan.get("scenes"):
        raise HTTPException(status_code=400, detail="Plan chưa có scene")
    missing = [x for x in ("ai_image_service", "video_ai_service") if not hasattr(request.app.state, x)]
    if missing:
        raise HTTPException(status_code=409, detail="AUTO PRODUCE thiếu module runtime: " + ", ".join(missing))
    try:
        jid = _producer_jobs(request).start(body.plan, body.quality, fast_mode=body.fast_mode)
        return {"ok": True, "job_id": jid, "status_url": f"/api/ai-video-director/produce/{jid}"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/produce/{job_id}")
def produce_status(job_id: str, request: Request):
    try:
        return _producer_jobs(request).get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy AUTO PRODUCE job")



@router.get("/produce/{job_id}/preview")
def produce_preview(job_id: str, request: Request):
    try:
        job = _producer_jobs(request).get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy AUTO PRODUCE job")
    folder = Path(job.get("folder") or "").resolve()
    root = (_base(request) / "data" / "ai_video_director" / "productions").resolve()
    if not folder.is_dir() or root not in folder.parents:
        raise HTTPException(status_code=404, detail="Chưa có preview")
    # Atomic file naming: all FFmpeg/shutil outputs are written to .tmp first,
    # then atomically renamed to the final name.  A file at its final path
    # (without .tmp suffix) is guaranteed to be complete and safe to serve.
    # No mtime grace window needed.
    candidates = []
    final = folder / "FINAL_VIDEO.mp4"
    mixed = folder / "MIXED_VIDEO.mp4"
    visual = folder / "visual_master.mp4"
    for f in (final, mixed, visual):
        if f.is_file():
            candidates.append(f)
    scenes = folder / "scenes"
    if scenes.is_dir():
        candidates += sorted(scenes.glob("scene_*_final.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
        candidates += sorted(scenes.glob("scene_*_raw.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
        candidates += sorted(scenes.glob("scene_*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
    anchor = folder / "character_anchor.png"
    if anchor.is_file():
        candidates.append(anchor)
    if not candidates:
        raise HTTPException(status_code=404, detail="Chưa có preview")
    f = max(candidates, key=lambda x: x.stat().st_mtime)
    if f.suffix.lower() == ".mp4":
        return FileResponse(f, media_type="video/mp4", filename=f.name)
    return FileResponse(f, media_type="image/png", filename=f.name)

@router.post("/produce/{job_id}/cancel")
def cancel_produce(job_id: str, request: Request):
    return {"cancelled": _producer_jobs(request).cancel(job_id)}


@router.get("/produce/{job_id}/download")
def download_produce(job_id: str, request: Request):
    try:
        job = _producer_jobs(request).get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy AUTO PRODUCE job")
    result = job.get("result") or {}
    final = result.get("final_video")
    if job.get("status") != "done" or not final:
        raise HTTPException(status_code=409, detail="Video chưa hoàn tất")
    path = Path(final).resolve()
    root = (_base(request) / "data" / "ai_video_director" / "productions").resolve()
    if not path.is_file() or root not in path.parents:
        raise HTTPException(status_code=404, detail="Không tìm thấy FINAL_VIDEO.mp4")
    return FileResponse(path, media_type="video/mp4", filename="FINAL_VIDEO.mp4")
