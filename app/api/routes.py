from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.schemas import EditorCutRequest, ProjectCreateRequest, RenderRequest, VideoCutRequest, VideoMergeRequest
from app.modules.video_editor.errors import VideoEditorError

router = APIRouter(prefix="/api")


def _editor_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))




def _video_media_type(path: Path) -> str:
    return {
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
    }.get(path.suffix.lower(), "video/mp4")


def _save_upload(upload: UploadFile, parent: Path) -> Path:
    suffix = Path(upload.filename or "file.bin").suffix or ".bin"
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(delete=False, dir=parent, suffix=suffix) as target:
        shutil.copyfileobj(upload.file, target, length=1024 * 1024)
        return Path(target.name)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/editor/upload")
def editor_upload(request: Request, file: UploadFile = File(...)):
    temp_path = None
    try:
        temp_path = _save_upload(file, request.app.state.video_workspace.root / "_incoming")
        return request.app.state.video_workspace.create(temp_path, file.filename or "video.mp4")
    except (VideoEditorError, ValueError) as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise _editor_error(exc) from exc


@router.get("/editor/{session_id}")
def editor_status(session_id: str, request: Request):
    try:
        return request.app.state.video_workspace.describe(session_id)
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.get("/editor/{session_id}/media")
def editor_media(session_id: str, request: Request):
    try:
        path = request.app.state.video_workspace.current_path(session_id)
        return FileResponse(path, media_type=_video_media_type(path))
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.post("/editor/{session_id}/cut")
def editor_cut(session_id: str, payload: EditorCutRequest, request: Request):
    try:
        workspace = request.app.state.video_workspace
        output = workspace.next_output(session_id)
        request.app.state.video_editor.cut(workspace.current_path(session_id), output, payload.start, payload.end)
        return workspace.add_version(session_id, output, f"Cắt {payload.start:.2f}s → {payload.end:.2f}s")
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.post("/editor/{session_id}/append")
def editor_append(session_id: str, request: Request, file: UploadFile = File(...), position: str = Form("after")):
    temp_path = None
    try:
        workspace = request.app.state.video_workspace
        current = workspace.current_path(session_id)
        temp_path = _save_upload(file, workspace.folder(session_id))
        output = workspace.next_output(session_id)
        sources = [temp_path, current] if position == "before" else [current, temp_path]
        request.app.state.video_editor.merge(sources, output)
        where = "đầu" if position == "before" else "cuối"
        result = workspace.add_version(session_id, output, f"Ghép {file.filename} vào {where}")
        temp_path.unlink(missing_ok=True)
        return result
    except (VideoEditorError, ValueError) as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise _editor_error(exc) from exc


@router.post("/editor/{session_id}/asset")
def editor_asset(session_id: str, request: Request, file: UploadFile = File(...)):
    temp_path = None
    try:
        workspace = request.app.state.video_workspace
        temp_path = _save_upload(file, workspace.folder(session_id) / "_asset_incoming")
        return workspace.save_asset(session_id, temp_path, file.filename or "image.png")
    except (VideoEditorError, ValueError) as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise _editor_error(exc) from exc


@router.get("/editor/{session_id}/asset/{asset_id}")
def editor_asset_media(session_id: str, asset_id: str, request: Request):
    try:
        return FileResponse(request.app.state.video_workspace.asset_path(session_id, asset_id))
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.post("/editor/{session_id}/render")
def editor_render(session_id: str, payload: RenderRequest, request: Request):
    try:
        workspace = request.app.state.video_workspace
        info = workspace.describe(session_id)
        output = workspace.folder(session_id) / "final_export.mp4"
        request.app.state.video_editor.render(
            workspace.current_path(session_id), output,
            [layer.model_dump() for layer in payload.layers], workspace, session_id,
        )
        stem = Path(info["original_name"]).stem or "video"
        return FileResponse(output, media_type="video/mp4", filename=f"{stem}_edited.mp4")
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.post("/editor/{session_id}/undo")
def editor_undo(session_id: str, request: Request):
    try:
        return request.app.state.video_workspace.undo(session_id)
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.get("/editor/{session_id}/download")
def editor_download(session_id: str, request: Request):
    try:
        workspace = request.app.state.video_workspace
        info = workspace.describe(session_id)
        path = workspace.current_path(session_id)
        stem = Path(info["original_name"]).stem or "video"
        return FileResponse(path, media_type=_video_media_type(path), filename=f"{stem}_edited{path.suffix.lower() or '.mp4'}")
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


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


@router.post("/video/cut")
def cut_video(payload: VideoCutRequest, request: Request):
    try:
        output = request.app.state.video_editor.cut(payload.source, payload.output, payload.start, payload.end)
        return {"status": "ok", "operation": "cut", "output": str(output)}
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc


@router.post("/video/merge")
def merge_videos(payload: VideoMergeRequest, request: Request):
    try:
        output = request.app.state.video_editor.merge(payload.sources, payload.output)
        return {"status": "ok", "operation": "merge", "output": str(output)}
    except (VideoEditorError, ValueError) as exc:
        raise _editor_error(exc) from exc
