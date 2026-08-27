from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/jobs", tags=["job-control"])


@router.post("/cancel-all")
def cancel_all(request: Request):
    managers = [
        ("ai_image", getattr(request.app.state, "ai_image_jobs", None)),
        ("model_3d", getattr(request.app.state, "model_3d_jobs", None)),
        ("video_cleanup", getattr(request.app.state, "video_cleanup_jobs", None)),
        ("facebook", getattr(request.app.state, "facebook_video_jobs", None)),
    ]
    detail = {}
    total = 0
    for name, manager in managers:
        count = int(manager.cancel_all()) if manager and hasattr(manager, "cancel_all") else 0
        detail[name] = count
        total += count
    return {"ok": True, "cancelled": total, "detail": detail}
