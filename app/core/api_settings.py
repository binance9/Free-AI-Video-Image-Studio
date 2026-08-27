"""Free-local AI status and optional one-click dependency installer."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from app.core.shared_services import dependency_status

router = APIRouter(prefix="/api/settings", tags=["local-ai"])
_INSTALLER = None


@router.get("/local-ai")
def local_ai_status(request: Request):
    data = dependency_status(request.app.state.model_dir)
    global _INSTALLER
    data["installing"] = bool(_INSTALLER and _INSTALLER.poll() is None)
    return data


@router.post("/install-local-ai")
def install_local_ai(request: Request):
    global _INSTALLER
    if _INSTALLER and _INSTALLER.poll() is None:
        return {"started": False, "message": "Đang cài AI local"}
    root = Path(__file__).resolve().parents[2]
    req = root / "requirements_local_ai.txt"
    if not req.is_file():
        raise HTTPException(status_code=500, detail="Thiếu requirements_local_ai.txt")
    log = root / "data" / "local_ai_install.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log, "w", encoding="utf-8")
    try:
        _INSTALLER = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            cwd=str(root), stdout=handle, stderr=subprocess.STDOUT,
        )
        handle.close()
    except Exception as exc:
        handle.close()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"started": True, "message": "Đã bắt đầu cài gói AI local miễn phí", "log": str(log)}
