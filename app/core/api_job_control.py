from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/jobs", tags=["job-control"])

# Trang thai duoc coi la "dang chay" tren MOI job manager trong app - tat ca
# _jobs dict trong du an deu dung chung quy uoc {"status": "queued"/"running"
# /"cancelling"/"done"/"error"/"cancelled"}, nen 1 helper dua tren vit (duck
# typing) o day dung duoc cho ca cac manager chua co cancel_all() rieng.
_ACTIVE_STATUSES = {"queued", "running", "cancelling"}


def _managers(state: Any) -> list[tuple[str, Any]]:
    """Liet ke MOI nguon job trong toan bo app - dung cho ca /status (kiem
    tra "co dang chay khong" truoc khi tat bot) va /cancel-all lan
    /api/system/shutdown (dung chung ham nay de khong bi sot module nao).
    Vai module (ban_do_3d, character_2d) chi tao manager/service vao
    app.state khi API cua no duoc goi lan dau - getattr(..., None) tra ve
    None mot cach an toan neu chua tung dung toi."""
    return [
        ("ai_image", getattr(state, "ai_image_jobs", None)),
        ("model_3d", getattr(state, "model_3d_jobs", None)),
        ("game_ready_3d", getattr(state, "game_ready_3d_jobs", None)),
        ("do_vat_3d", getattr(state, "do_vat_3d_jobs", None)),
        ("video_cleanup", getattr(state, "video_cleanup_jobs", None)),
        ("facebook", getattr(state, "facebook_video_jobs", None)),
        ("tai_video_web", getattr(state, "tai_video_web_jobs", None)),
        ("character_2d", getattr(state, "character_2d_jobs", None)),
        ("ban_do_3d", getattr(state, "ban_do_3d_service", None)),
    ]


def _active_count(manager: Any) -> int:
    jobs = getattr(manager, "_jobs", None) if manager is not None else None
    if not isinstance(jobs, dict):
        return 0
    try:
        snapshot = list(jobs.values())
    except Exception:
        return 0
    return sum(1 for j in snapshot if isinstance(j, dict) and j.get("status") in _ACTIVE_STATUSES)


def count_active_jobs(state: Any) -> dict:
    """App-wide snapshot: co job nao dang chay/xep hang o BAT KY module
    nao khong. Dung boi nut "TAT BOT" o frontend de quyet dinh co can hoi
    xac nhan hay tat ngay, va la nguon that cho /api/system/shutdown."""
    detail = {name: _active_count(manager) for name, manager in _managers(state)}
    total = sum(detail.values())
    return {"busy": total > 0, "total": total, "detail": detail}


def cancel_all_jobs(state: Any) -> dict:
    detail: dict[str, int] = {}
    total = 0
    for name, manager in _managers(state):
        count = 0
        if manager is not None and hasattr(manager, "cancel_all"):
            try:
                count = int(manager.cancel_all())
            except Exception:
                count = 0
        detail[name] = count
        total += count
    return {"ok": True, "cancelled": total, "detail": detail}


@router.get("/status")
def jobs_status(request: Request):
    return count_active_jobs(request.app.state)


@router.post("/cancel-all")
def cancel_all(request: Request):
    return cancel_all_jobs(request.app.state)
