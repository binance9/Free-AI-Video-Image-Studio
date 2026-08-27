from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/3d/game-ready", tags=["3d-game-ready"])


class GameReadyRequest(BaseModel):
    asset_id: str = Field(min_length=8, max_length=80)
    target_faces: int = Field(default=45000, ge=18000, le=80000)


@router.get("/status")
def game_ready_status(request: Request):
    return request.app.state.game_ready_3d_service.status()


@router.post("/jobs")
def start_game_ready(payload: GameReadyRequest, request: Request):
    try:
        job_id = request.app.state.game_ready_3d_jobs.start(payload.asset_id, payload.target_faces)
        return {"job_id": job_id, "status_url": f"/api/3d/game-ready/jobs/{job_id}"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def game_ready_job(job_id: str, request: Request):
    try:
        payload = request.app.state.game_ready_3d_jobs.get(job_id)
        result = payload.get("result")
        if result:
            result = dict(result)
            result["model_url"] = f"/api/3d/model/{result['asset_id']}"
            result["viewer_url"] = f"/api/3d/view/{result['asset_id']}"
            payload["result"] = result
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
