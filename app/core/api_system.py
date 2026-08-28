from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.api_job_control import cancel_all_jobs
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


def _kill_own_process_tree(delay_seconds: float = 0.6) -> None:
    """Ha guc TOAN BO cay tien trinh cua CHINH server nay (moi FFmpeg / python
    worker con da spawn deu la con/chau cua PID nay) sau 1 khoang tre ngan de
    HTTP response kip gui ve trinh duyet truoc khi server chet.

    Chi dung PID cua CHINH tien trinh dang chay (os.getpid()) cong "/T" (chi
    con chau cua PID do) - khong bao gio dung toi PID cua chuong trinh khac
    tren may, du la taskkill co quyen he thong. Day cung la co che duy nhat
    dam bao giai phong GPU/VRAM va dong moi file/job dang giu: khi tien
    trinh (va moi tien trinh con) bi killed, he dieu hanh/driver GPU tu thu
    hoi toan bo tai nguyen (VRAM, file handle, socket) cua no ngay lap tuc,
    khong can don dep thu cong tung phan.
    """
    pid = os.getpid()

    def _kill() -> None:
        time.sleep(delay_seconds)
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        else:
            import signal
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                os.kill(pid, signal.SIGKILL)

    threading.Thread(target=_kill, daemon=True, name="aivf-shutdown").start()


@router.post("/shutdown")
def shutdown(request: Request):
    """Nut "⏻ TẮT BOT": dừng toàn bộ job đang chạy (best-effort, để job tự
    cập nhật trạng thái "cancelled" trước khi chết) rồi hạ gục toàn bộ cây
    tiến trình của server (FFmpeg, Python worker, model con...) và đóng
    cổng đang lắng nghe (8123 mặc định). Trả response NGAY trước khi tiến
    trình thật sự bị kill (xem _kill_own_process_tree)."""
    cancelled = cancel_all_jobs(request.app.state)
    _kill_own_process_tree()
    return {"ok": True, "message": "Đang tắt AI Video Factory…", "cancelled_jobs": cancelled}
