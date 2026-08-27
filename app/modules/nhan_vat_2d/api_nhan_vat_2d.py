"""Character 2D Studio routes integrated into the main AI Video Factory app."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.modules.nhan_vat_2d import Character2DService, CharacterProfile

router = APIRouter(prefix="/api/character-2d", tags=["character-2d"])


def _service(request: Request) -> Character2DService:
    svc = getattr(request.app.state, "character_2d_service", None)
    if svc is None:
        raise RuntimeError("Character 2D service is not initialized")
    return svc


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/api/character-2d/output?path={quote(str(path), safe='')}"


def _decorate(payload: dict) -> dict:
    out = dict(payload)
    out["image_url"] = _media_url(out.get("image") or out.get("anchor"))
    out["best_rejected_url"] = _media_url(out.get("best_rejected_candidate"))
    gate = out.get("export_gate") or {}
    debug = gate.get("gate_debug") or {}
    out["gate_summary"] = {
        "score": gate.get("quality_score"),
        "minimum": gate.get("minimum_score"),
        "identity": debug.get("identity_similarity"),
        "target_color": debug.get("target_color_score"),
        "weapon": debug.get("weapon_score"),
        "override": debug.get("high_confidence_export_override", False),
        "blockers": gate.get("blockers", []),
    }
    return out


@router.get("/status")
def status(request: Request):
    svc = _service(request)
    info = svc.image_service.engine_info()
    return {
        "ok": True,
        "version": "1.3.2",
        "engine": info,
        "ui_mode": "simple",
        "handoff_3d": True,
    }


@router.post("/create")
async def create_character(
    request: Request,
    prompt: str = Form(...),
    image: UploadFile | None = File(None),
    preset: str = Form("compact_game"),
    strength: float = Form(0.28),
    quality: str = Form("medium"),
):
    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        raise HTTPException(status_code=400, detail="Nhập yêu cầu tạo/chỉnh nhân vật trước")
    if quality not in {"fast", "medium", "high"}:
        quality = "medium"
    try:
        svc = _service(request)
        if image is not None and image.filename:
            raw = await image.read()
            if not raw:
                raise ValueError("Ảnh mẫu đang rỗng")
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("Ảnh mẫu tối đa 20 MB")
            result = svc.create_from_reference(
                raw,
                image.filename,
                prompt,
                size="1024x1024",
                style="fantasy",
                quality=quality,
                min_score=70,
                max_repairs=3,
                strength=strength,
                preset=preset,
            )
        else:
            profile = CharacterProfile.from_prompt(prompt)
            result = svc.create_anchor(
                profile,
                size="1024x1024",
                style="fantasy",
                quality=quality,
                mode="final",
                max_repairs=3,
                min_score=70,
                preset=preset,
            )
            result["operation"] = "generate-from-prompt"
        return _decorate(result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/output")
def output(path: str, request: Request):
    svc = _service(request)
    root = svc.root.resolve()
    target = Path(path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="File nằm ngoài Character 2D workspace") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh Character 2D")
    return FileResponse(target, media_type="image/png", headers={"Cache-Control": "no-store"})
