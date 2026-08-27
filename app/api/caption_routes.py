"""Free local automatic caption and translation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.modules.subtitle_local import extract_audio

router = APIRouter(prefix="/api", tags=["captions-local"])


class TranslateRequest(BaseModel):
    segments: list[dict] = Field(min_length=1, max_length=150)
    source_language: str = Field(default="en", min_length=2, max_length=40)
    target_language: str = Field(min_length=2, max_length=40)


@router.post("/editor/{session_id}/captions/transcribe")
def transcribe(session_id: str, request: Request):
    audio = None
    try:
        workspace = request.app.state.video_workspace
        audio = workspace.folder(session_id) / "_caption_audio.mp3"
        extract_audio(workspace.current_path(session_id), audio)
        return request.app.state.caption_service.transcribe(audio)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if audio:
            audio.unlink(missing_ok=True)


@router.post("/captions/translate")
def translate(payload: TranslateRequest, request: Request):
    try:
        rows = request.app.state.translation_service.translate_segments(
            payload.segments, payload.source_language, payload.target_language
        )
        return {"segments": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
