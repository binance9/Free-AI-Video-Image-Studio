from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from .service import CORE_VERSION, MODULES, NativeBrain
from app.modules.ga_maintenance.api_ga_maintenance import _healer as _maintenance_healer, JobHealRequest

router = APIRouter(prefix="/api/ga-brain", tags=["ga-brain"])
# Keep old build id so the existing launcher remains backward-compatible.
BUILD_VERSION = "v12-fast-natural-router"


class PlanRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    context: dict = Field(default_factory=dict)
    force_target: str | None = None
    optimize_only: bool = False


class RememberRequest(BaseModel):
    module: str
    settings: dict
    source: str = "manual"


class InteractRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    context: dict = Field(default_factory=dict)


class ToolResultRequest(BaseModel):
    report: dict = Field(default_factory=dict)


def _brain(request: Request):
    brain = getattr(request.app.state, "ga_native_brain", None)
    if brain is None or getattr(brain, "core_version", CORE_VERSION) != CORE_VERSION:
        root = Path(__file__).resolve().parents[3] / "data" / "ga_brain"
        brain = NativeBrain(root)
        brain.core_version = CORE_VERSION
        request.app.state.ga_native_brain = brain
    return brain


@router.get("/status")
def status(request: Request):
    b = _brain(request)
    return {
        "ok": True,
        "mode": "central-ai-core",
        "build_version": BUILD_VERSION,
        "core_version": CORE_VERSION,
        "interact_ready": callable(getattr(b, "interact", None)),
        "brain_class": type(b).__name__,
        "architecture": [
            "AI_CORE", "CONTEXT_MANAGER", "REFERENCE_RESOLVER", "INTENT_ROUTER", "PLANNER",
            "TOOL_REGISTRY", "PERMISSION_GATE", "REQUIREMENT_VALIDATOR", "EXECUTION_MANAGER", "TOOL_EXECUTOR",
            "RESULT_VERIFIER", "RESPONSE_ENGINE",
        ],
        "modules": MODULES,
        "ollama": b.models.status(),
        "vision": b.models.vision_status(),
        "memory_modules": list(b.memory.data.get("modules", {}).keys()),
        "route_stats": b.route_stats(),
    }


@router.get("/route-stats")
def route_stats(request: Request):
    b = _brain(request)
    return {"ok": True, "stats": b.route_stats(), "recent": b.route_log(50)}


@router.post("/interact")
def interact(body: InteractRequest, request: Request):
    try:
        return _brain(request).interact(body.message.strip(), context=body.context)
    except Exception as exc:
        raise HTTPException(400, f"AI_CORE: {type(exc).__name__}: {exc}") from exc


@router.post("/interact-with-image")
async def interact_with_image(
    request: Request,
    message: str = Form(...),
    context_json: str = Form("{}"),
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "reference.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Ảnh tham chiếu phải là PNG/JPG/WebP")
    raw = await file.read()
    if not raw or len(raw) > 20 * 1024 * 1024:
        raise HTTPException(400, "Ảnh tham chiếu phải nhỏ hơn 20 MB")
    try:
        context = json.loads(context_json or "{}")
        if not isinstance(context, dict):
            context = {}
    except Exception:
        context = {}
    fd, name = tempfile.mkstemp(prefix="ga_core_image_", suffix=suffix)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_bytes(raw)
        context["attachment"] = True
        context["attachment_name"] = file.filename or tmp.name
        return _brain(request).interact(
            message.strip(), context=context, image_path=tmp, image_name=file.filename or tmp.name
        )
    except Exception as exc:
        raise HTTPException(400, f"AI_CORE_IMAGE: {type(exc).__name__}: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/plan")
def plan(body: PlanRequest, request: Request):
    try:
        return _brain(request).plan(
            body.message.strip(),
            context=body.context,
            force_target=body.force_target,
            optimize_only=body.optimize_only,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/remember")
def remember(body: RememberRequest, request: Request):
    if body.module not in MODULES:
        raise HTTPException(400, "Module không hợp lệ")
    _brain(request).memory.remember(body.module, body.settings, body.source)
    return {"ok": True}


@router.post("/result")
def record_result(body: ToolResultRequest, request: Request):
    return {"ok": True, "verification": _brain(request).record_tool_result(body.report)}


@router.post("/heal-job")
def heal_job(body: JobHealRequest, request: Request):
    try:
        return _maintenance_healer(request).heal_job(body.scope, body.job_id, body.job_state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
