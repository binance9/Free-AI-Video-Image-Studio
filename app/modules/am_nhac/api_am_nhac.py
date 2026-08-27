"""Free local music library, uploads, recommendation and mixing endpoints."""
from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.modules.am_nhac import mix_music

router = APIRouter(prefix="/api", tags=["music-local"])


class MusicSearch(BaseModel):
    wish: str = Field(default="", max_length=300)
    limit: int = Field(default=18, ge=1, le=30)


class LibraryImport(BaseModel):
    track_id: str = Field(min_length=1, max_length=200)


class MusicApply(BaseModel):
    audio_id: str = Field(min_length=1, max_length=100)
    clip_duration: float = Field(default=15, ge=2, le=120)
    insert_at: float = Field(default=0, ge=0)
    volume: float = Field(default=0.35, ge=0, le=1.5)
    keep_original: bool = True
    smart_excerpt: bool = True


@router.post("/music/search")
def music_search(payload: MusicSearch, request: Request):
    try:
        result = request.app.state.music_library.search(payload.wish, payload.limit)
        for item in result["items"]:
            item["preview"] = f"/api/music/library/{item['id']}"
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/music/library/{track_id}")
def music_library_media(track_id: str, request: Request):
    try:
        path = request.app.state.music_library.path(track_id)
        return FileResponse(path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/editor/{session_id}/music/import-library")
def import_library(session_id: str, payload: LibraryImport, request: Request):
    temp = None
    try:
        source = request.app.state.music_library.path(payload.track_id)
        folder = request.app.state.video_workspace.folder(session_id)
        temp = folder / ("library_" + source.name)
        shutil.copy2(source, temp)
        return request.app.state.video_workspace.save_audio(session_id, temp, source.name)
    except Exception as exc:
        if temp:
            Path(temp).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/editor/{session_id}/music/upload")
def music_upload(session_id: str, request: Request, file: UploadFile = File(...)):
    temp = None
    try:
        folder = request.app.state.video_workspace.folder(session_id)
        suffix = Path(file.filename or "audio.mp3").suffix or ".mp3"
        with NamedTemporaryFile(delete=False, dir=folder, suffix=suffix) as target:
            shutil.copyfileobj(file.file, target, length=1024 * 1024)
            temp = Path(target.name)
        # Keep a free local-library copy for future keyword recommendation.
        library_copy = request.app.state.music_library.root / Path(file.filename or temp.name).name
        if library_copy.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}:
            shutil.copy2(temp, library_copy)
        return request.app.state.video_workspace.save_audio(session_id, temp, file.filename or "audio.mp3")
    except Exception as exc:
        if temp:
            temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/editor/{session_id}/music/apply")
def apply_music(session_id: str, payload: MusicApply, request: Request):
    try:
        workspace = request.app.state.video_workspace
        output = workspace.next_output(session_id)
        result = mix_music(
            workspace.current_path(session_id), workspace.audio_path(session_id, payload.audio_id), output,
            clip_duration=payload.clip_duration, insert_at=payload.insert_at, volume=payload.volume,
            keep_original=payload.keep_original, smart_excerpt=payload.smart_excerpt,
        )
        info = workspace.add_version(session_id, result["output"], f"Thêm nhạc {payload.clip_duration:.0f}s")
        info["music_excerpt_start"] = result["source_start"]
        return info
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
