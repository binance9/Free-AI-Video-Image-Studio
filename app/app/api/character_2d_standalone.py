from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.modules.character_2d_addon import Character2DService, CharacterProfile
from app.modules.character_2d_addon.spec_parser import parse_character_spec

app = FastAPI(title="AI Video Factory Character 2D Addon", version="1.3.1")
service = Character2DService()


class Character2DRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    action: str = Field(default="run")
    frames: int = Field(default=4, ge=1, le=8)
    directions: list[str] = Field(default_factory=lambda: [
        "down", "down_left", "left", "up_left", "up", "up_right", "right", "down_right"
    ])
    size: str = "1024x1024"
    style: str = "fantasy"
    quality: str = "high"
    min_score: int = Field(default=72, ge=50, le=95)
    max_repairs: int = Field(default=2, ge=0, le=3)
    preset: str = Field(default="compact_game")


@app.get("/health")
def health():
    return {"ok": True, "service": "character-2d-addon", "version": "1.3.1", "default_preset": "compact_game"}


@app.post("/character-2d/spec")
def parse_spec(payload: Character2DRequest):
    try:
        return service.parse_spec(payload.prompt, payload.preset)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/character-2d/reference")
def reference_info(payload: Character2DRequest):
    try:
        spec = parse_character_spec(payload.prompt)
        spec.render_preset = payload.preset
        return service.reference_library.info(spec)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/character-2d/engine")
def engine_info():
    return service.image_service.engine_info()


@app.post("/character-2d/engine/warmup")
def engine_warmup():
    try:
        return service.image_service.warmup()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/character-2d/preview")
def create_preview(payload: Character2DRequest):
    try:
        profile = CharacterProfile.from_prompt(payload.prompt)
        return service.create_anchor(
            profile, size=payload.size, style=payload.style, quality="medium", mode="preview",
            max_repairs=0, min_score=max(60, payload.min_score - 8), preset=payload.preset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/character-2d/anchor")
def create_anchor(payload: Character2DRequest):
    try:
        profile = CharacterProfile.from_prompt(payload.prompt)
        return service.create_anchor(
            profile, size=payload.size, style=payload.style, quality=payload.quality, mode="final",
            max_repairs=payload.max_repairs, min_score=payload.min_score, preset=payload.preset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/character-2d/sheet")
def create_sheet(payload: Character2DRequest):
    try:
        profile = CharacterProfile.from_prompt(payload.prompt)
        return service.create_action_sheet(
            profile, directions=payload.directions, action=payload.action, frames=payload.frames,
            size=payload.size, style=payload.style, quality=payload.quality, min_score=payload.min_score, preset=payload.preset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/character-2d/ui", include_in_schema=False)
def character_2d_ui():
    ui = Path(__file__).resolve().parents[1] / "web" / "character_2d" / "index.html"
    if not ui.is_file():
        raise HTTPException(status_code=404, detail="Character 2D UI not found")
    return FileResponse(ui, media_type="text/html")


@app.post("/character-2d/from-reference-simple")
async def create_from_reference_simple(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    preset: str = Form("compact_game"),
    strength: float = Form(0.28),
):
    try:
        raw = await image.read()
        if not raw:
            raise ValueError("Reference image is empty")
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("Reference image is too large; maximum is 20 MB")
        return service.create_from_reference(
            raw, image.filename or "reference.png", prompt,
            size="1024x1024", style="fantasy", quality="medium", min_score=70,
            max_repairs=3, strength=strength, preset=preset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/character-2d/from-reference", include_in_schema=False)
async def create_from_reference(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    style: str = Form("fantasy"),
    quality: str = Form("medium"),
    min_score: int = Form(70),
    max_repairs: int = Form(3),
    strength: float = Form(0.28),
    preset: str = Form("compact_game"),
):
    try:
        raw = await image.read()
        if not raw:
            raise ValueError("Reference image is empty")
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("Reference image is too large; maximum is 20 MB")
        return service.create_from_reference(
            raw, image.filename or "reference.png", prompt,
            size=size, style=style, quality=quality, min_score=min_score,
            max_repairs=max_repairs, strength=strength, preset=preset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/character-2d/file")
def serve_file(path: str):
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    return FileResponse(file_path)
