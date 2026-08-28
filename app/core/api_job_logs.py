from __future__ import annotations

import asyncio
import json
import time
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.core.job_log_broker import job_log_broker


router = APIRouter(prefix="/api/job-logs", tags=["job-logs"])

_SOURCES: dict[str, tuple[str, str]] = {
    "map_hd": ("ban_do_3d_service", "get"),
    "image": ("ai_image_jobs", "get"),
    "character_2d": ("character_2d_jobs", "get"),
    "character_3d": ("model_3d_jobs", "get"),
    "object_3d": ("do_vat_3d_jobs", "get"),
    "video_cleanup": ("video_cleanup_jobs", "get"),
    "facebook_video": ("facebook_video_jobs", "get"),
    "web_video": ("tai_video_web_jobs", "get"),
}
_DONE = {"done", "completed", "error", "failed", "cancelled"}


def _getter(request: Request, scope: str) -> Callable[[str], dict]:
    source = _SOURCES.get(scope)
    if not source:
        raise HTTPException(404, "Loại job không hỗ trợ log")
    service = getattr(request.app.state, source[0], None)
    if service is None and scope == "map_hd":
        from app.modules.ban_do_3d.api_ban_do_3d import svc
        service = svc(request)
    if service is None and scope == "character_2d":
        from app.modules.nhan_vat_2d.api_nhan_vat_2d import _jobs
        service = _jobs(request)
    if service is None:
        raise HTTPException(503, "Dịch vụ job chưa sẵn sàng")
    return getattr(service, source[1])


def _event(kind: str, payload: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _gate_rejected(job: dict) -> bool:
    """Mot so module hoan tat job KHONG loi (khong exception) nhung GATE
    CHAT LUONG rieng cua module do tu choi ket qua - vi du that da phat hien
    qua test that: character_2d tra status="done" nhung result.accepted=
    false/result.status="rejected" (CLIP gate tu choi ca 5 lan thu), map_hd
    tra status="completed" nhung master_pass=false (sharpness/border gate).
    Neu khong tinh rieng truong hop nay, terminal se hien SAI "✓ HOAN THANH"
    cho 1 ket qua thuc ra BI TU CHOI - can bao "✕ LOI" dung nhu yeu cau."""
    if job.get("master_pass") is False:
        return True
    result = job.get("result")
    if isinstance(result, dict):
        if result.get("accepted") is False:
            return True
        if str(result.get("status", "")).lower() == "rejected":
            return True
    return False


def _output(job: dict, scope: str):
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    for key in ("model_url", "image_url", "url", "download_url", "output", "output_path", "file"):
        if result.get(key):
            return result[key]
        if job.get(key):
            return job[key]
    asset_id = result.get("asset_id")
    if asset_id and scope == "character_3d":
        return f"/api/3d/model/{asset_id}"
    if asset_id and scope == "object_3d":
        return f"/api/do-vat-3d/output/{asset_id}"
    editor = result.get("editor") if isinstance(result.get("editor"), dict) else {}
    if editor.get("session_id"):
        return f"/api/editor/{editor['session_id']}/media"
    return job.get("overview_url") or job.get("preview_url")


@router.get("/{scope}/{job_id}/stream")
async def stream_job_log(request: Request, scope: str, job_id: str, mode: str = "normal", since: int = 0):
    if not job_id or len(job_id) > 128 or not job_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "job_id không hợp lệ")
    getter = _getter(request, scope)
    debug = mode.lower() == "debug"
    try:
        getter(job_id)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy job")

    async def generate():
        started = time.monotonic()
        last_signature = None
        # "since" cho phep client (vd khi doi NORMAL/DEBUG giua chung job, mo
        # 1 EventSource MOI) tiep tuc tu vi tri da xem, khong phat lai tu dau
        # toan bo raw stdout/stderr da cache - tranh log bi LAP LAI (bug that
        # da phat hien: doi mode giua job lam "Creating job...", canh bao CLIP
        # truncate... hien 2 lan).
        raw_cursor = max(0, int(since))
        # "Creating job..." duoc job_terminal.js tu them cuc bo khi bat dau 1
        # job THAT SU MOI (preserve=false) - KHONG phat lai o day nua, vi khi
        # client mo EventSource MOI de doi NORMAL/DEBUG giua chung 1 job
        # (preserve=true), dong nay se hien LAP LAI (bug that da phat hien
        # qua test that: "Creating job..." hien 2 lan khi doi mode).
        while not await request.is_disconnected():
            try:
                for raw in job_log_broker.after(scope, job_id, raw_cursor):
                    raw_cursor = max(raw_cursor, raw["seq"])
                    if debug or raw["level"] in {"warning", "error", "success"}:
                        yield _event("log", {"job_id": job_id, "scope": scope, "status": "running", "stage": raw["channel"], "message": raw["message"], "level": raw["level"], "raw": True, "seq": raw["seq"]})
                job = getter(job_id)
                status = str(job.get("status") or "running").lower()
                terminal_status = "failed" if status in {"done", "completed"} and _gate_rejected(job) else status
                stage = str(job.get("stage") or status)
                detail = str(job.get("detail") or job.get("message") or "")
                error = str(job.get("error") or "")
                progress = max(0, min(100, float(job.get("progress") or 0)))
                signature = (status, stage, detail, error, progress)
                if signature != last_signature:
                    level = "error" if terminal_status in {"error", "failed"} else "warning" if "warning" in detail.lower() else "success" if terminal_status in {"done", "completed"} else "info"
                    payload = {"job_id": job_id, "scope": scope, "status": terminal_status, "stage": stage, "message": error or detail or stage, "progress": progress, "level": level}
                    if debug:
                        payload["debug"] = {k: v for k, v in job.items() if k not in {"result", "job_dir"}}
                    yield _event("log", payload)
                    last_signature = signature
                if status in _DONE:
                    yield _event("end", {"job_id": job_id, "status": terminal_status, "stage": stage, "message": error or detail or stage, "progress": progress, "elapsed_seconds": job.get("elapsed_seconds") or round(time.monotonic() - started, 2), "output": _output(job, scope)})
                    break
            except KeyError:
                yield _event("end", {"job_id": job_id, "status": "error", "stage": "Không tìm thấy job", "message": "Job đã bị xóa khỏi bộ nhớ"})
                break
            except Exception as exc:
                yield _event("log", {"job_id": job_id, "status": "running", "level": "warning", "stage": "Mất kết nối trạng thái", "message": str(exc)})
            await asyncio.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
