"""API routes for the standalone video-cut module.

Two routes moved here from app.modules.chinh_sua_video (see that module's
README_MODULE.md for the history):
- POST /api/video/cut - stateless, single-shot cut (source/output paths).
- POST /api/editor/{session_id}/cut - cut within a shared editor session.
  Still touches app.state.video_workspace (chinh_sua_video.workspace) since
  the session/undo/versioning system is intentionally shared infra used by
  many modules - only the actual CUT ENGINE is independent here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.modules.chinh_sua_video.errors import VideoEditorError

from .errors import CatVideoError
from .schemas import EditorCutRequest, VideoCutRequest
from .service import cut_video

router = APIRouter(prefix="/api")


def _cut_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/video/cut")
def cut_video_standalone(payload: VideoCutRequest):
    try:
        output = cut_video(payload.source, payload.output, payload.start, payload.end)
        return {"status": "ok", "operation": "cut", "output": str(output)}
    except (CatVideoError, ValueError) as exc:
        raise _cut_error(exc) from exc


@router.post("/editor/{session_id}/cut")
def editor_cut(session_id: str, payload: EditorCutRequest, request: Request):
    try:
        workspace = request.app.state.video_workspace
        output = workspace.next_output(session_id)
        cut_video(workspace.current_path(session_id), output, payload.start, payload.end)
        return workspace.add_version(session_id, output, f"Cắt {payload.start:.2f}s → {payload.end:.2f}s")
    except (CatVideoError, VideoEditorError, ValueError) as exc:
        raise _cut_error(exc) from exc
