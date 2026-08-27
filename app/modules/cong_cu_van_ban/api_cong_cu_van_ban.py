"""Text-template catalog endpoints."""
from fastapi import APIRouter
from app.modules.cong_cu_van_ban import list_presets

router = APIRouter(prefix="/api/text", tags=["text"])


@router.get("/presets")
def presets():
    return {"items": list_presets()}
