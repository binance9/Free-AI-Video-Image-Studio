"""System-wide routes not owned by any single feature module: health check
and project bootstrap/listing (backed by DirectorAI + ProjectMemory)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api")


class ProjectCreateRequest(BaseModel):
    command: str = Field(min_length=3, max_length=5000)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreateRequest, request: Request):
    try:
        return request.app.state.director.create_project(payload.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects")
def list_projects(request: Request):
    return {"items": request.app.state.memory.list_projects()}


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request):
    project = request.app.state.memory.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
