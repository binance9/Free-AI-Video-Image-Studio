from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ga-maintenance", tags=["ga-maintenance"])

class AuditRequest(BaseModel):
    cleanup: bool = True
    repair: bool = True

class JobHealRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=64)
    job_id: str = Field(min_length=1, max_length=128)
    job_state: dict = {}

class ApplyPatchRequest(BaseModel):
    patch_id: str = Field(min_length=1, max_length=64)

def _root():
    return Path(__file__).resolve().parents[3]

def _auditor():
    from .service import SafeProjectAuditor
    return SafeProjectAuditor(_root())

def _healer(request: Request):
    from .self_heal import RuntimeSelfHealer
    h = getattr(request.app.state, "ga_runtime_self_healer", None)
    if h is None:
        h = RuntimeSelfHealer(_root())
        request.app.state.ga_runtime_self_healer = h
    return h

@router.get("/status")
def status(request: Request):
    return {
        "ok": True,
        "mode": "safe-runtime-self-heal-v5.2-lazy",
        "loaded": getattr(request.app.state, "ga_runtime_self_healer", None) is not None,
        "policy": {
            "startup": "No maintenance scan/repair/restart at startup.",
            "repair": "Load self-heal only after a real job error or explicit audit request.",
            "restart": "Never auto-restart Windows launcher."
        }
    }

@router.post("/audit")
def audit(body: AuditRequest, request: Request):
    result = _auditor().audit(cleanup=body.cleanup, repair=body.repair)
    if result.get("ok"):
        try:
            result["last_known_good"] = _healer(request).lkg.ensure()
        except Exception as exc:
            result["last_known_good"] = {"ok": False, "error": str(exc)}
    return result

@router.post("/job-heal")
def job_heal(body: JobHealRequest, request: Request):
    try:
        return _healer(request).heal_job(body.scope, body.job_id, body.job_state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/apply-patch")
def apply_patch(body: ApplyPatchRequest, request: Request):
    return _healer(request).apply_pending_patch(body.patch_id)

@router.get("/runtime-incidents")
def runtime_incidents(request: Request, after: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    store = getattr(request.app.state, "ga_runtime_incidents", None)
    if store is None:
        return {"items": []}
    return {"items": store.after(after_id=after, limit=limit)}
