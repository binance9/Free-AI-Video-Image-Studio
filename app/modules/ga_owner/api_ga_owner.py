from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from .voice_owner import OwnerVoiceVerifier

router = APIRouter(prefix="/api/ga-owner", tags=["ga-owner"])


def _root(request: Request) -> Path:
    base = Path(__file__).resolve().parents[3]
    root = base / "data" / "ga_owner"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _voice(request: Request):
    v = getattr(request.app.state, "ga_owner_voice", None)
    if v is None:
        v = OwnerVoiceVerifier(_root(request) / "owner_voice.json")
        request.app.state.ga_owner_voice = v
    return v


@router.get("/status")
def status(request: Request):
    v = _voice(request)
    brain = getattr(request.app.state, "ga_native_brain", None)
    ollama = brain.ollama.status() if brain is not None else {
        "ok": None, "model": "qwen3:8b", "installed": None,
    }
    return {
        "ok": True,
        "architecture": "one-central-native-brain",
        "ollama": ollama,
        "voice": {
            "available": v.available,
            "enrolled": v.enrolled,
            "pending_samples": len(v.samples),
            "target_samples": 5,
            "note": "Voiceprint tiện dụng; không chống replay/voice-clone tinh vi.",
        },
    }


@router.post("/upload")
async def upload_attachment(request: Request, file: UploadFile = File(...)):
    suffix = Path(file.filename or "image.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Gà nhận ảnh PNG/JPG/WebP")
    data = await file.read()
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(400, "Ảnh phải nhỏ hơn 20 MB")
    folder = _root(request) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    aid = uuid.uuid4().hex
    (folder / (aid + suffix)).write_bytes(data)
    return {"attachment_id": aid, "name": file.filename, "size": len(data)}


@router.post("/voice/enroll/reset")
def voice_reset(request: Request):
    v = _voice(request)
    if not v.available:
        raise HTTPException(503, "Thiếu thư viện voiceprint")
    v.reset_enrollment()
    return {"ok": True, "count": 0, "target": 5}


@router.post("/voice/enroll/sample")
async def voice_sample(request: Request):
    v = _voice(request)
    if not v.available:
        raise HTTPException(503, "Thiếu thư viện voiceprint")
    raw = await request.body()
    try:
        return {"ok": True, **v.add_enrollment_sample(raw, 16000, 5)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/voice/verify")
async def voice_verify(request: Request):
    v = _voice(request)
    if not v.available:
        raise HTTPException(503, "Thiếu thư viện voiceprint")
    if not v.enrolled:
        raise HTTPException(409, "Chưa đăng ký giọng chủ")
    raw = await request.body()
    try:
        ok, score = v.verify(raw, 16000)
        return {"ok": bool(ok), "score": round(float(score), 4)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
