from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/3d/library", tags=["3d-library"])


class SaveLibraryRequest(BaseModel):
    asset_id: str = Field(min_length=4, max_length=120)
    name: str = Field(default="Model 3D", max_length=80)


@router.get("")
def list_library(request: Request):
    return {"ok": True, "items": request.app.state.model_3d_library.list_items()}


@router.post("/save")
def save_to_library(payload: SaveLibraryRequest, request: Request):
    try:
        item = request.app.state.model_3d_library.save(payload.asset_id, name=payload.name)
        return {"ok": True, "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{item_id}/model")
def library_model(item_id: str, request: Request):
    try:
        path = request.app.state.model_3d_library.model_path(item_id)
        return FileResponse(path, media_type="model/gltf-binary", filename=f"{item_id}.glb")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{item_id}/restore")
def restore_library_model(item_id: str, request: Request):
    try:
        result = request.app.state.model_3d_library.restore(item_id)
        asset_id = result["asset_id"]
        return {"ok": True, **result, "model_url": f"/api/3d/model/{asset_id}", "viewer_url": f"/api/3d/view/{asset_id}"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{item_id}")
def delete_library_model(item_id: str, request: Request):
    try:
        return request.app.state.model_3d_library.delete(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
