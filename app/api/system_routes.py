from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings

router = APIRouter(prefix="/api/system", tags=["system"])

FOLDERS = {
    "editor": settings.editor_dir,
    "images": settings.ai_image_dir,
    "3d": settings.model_3d_dir,
    "facebook": settings.facebook_download_dir,
    "cleanup": settings.video_cleanup_jobs_dir,
}



@router.post("/open-folder")
def open_folder(kind: str = Query("editor")):
    path = FOLDERS.get(kind)
    if path is None:
        raise HTTPException(status_code=400, detail="Thư mục kết quả không hợp lệ")
    try:
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", str(path)], shell=False)
            return {"ok": True, "kind": kind, "path": str(path)}
        return {"ok": True, "kind": kind, "path": str(path), "opened": False}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Không mở được thư mục: {exc}") from exc


@router.get("/folders")
def folders():
    return {"items": {name: str(path) for name, path in FOLDERS.items()}}
