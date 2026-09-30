from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT_START = 8123
PORT_END = 8199
LOG = ROOT / "data" / "ga_maintenance" / "startup_error.log"
MODE = ROOT / "data" / "ga_maintenance" / "startup_mode.txt"

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# System/startup log sink for the in-web terminal (UI-only feature - this is
# pure observability, it never touches launcher control flow: single-instance
# check, port selection and uvicorn startup below are all unchanged). Same
# process as the backend (uvicorn.run(app, ...) below runs in-process, not a
# subprocess), so this in-memory broker instance is the exact one the web
# terminal reads from via /api/job-logs/system/startup/stream.
from app.core.job_log_broker import job_log_broker  # noqa: E402

job_log_broker.install()
job_log_broker.publish("system", "startup", "Launcher: đã nhận lệnh khởi động (P).")

def get_json(url: str, timeout: float = 0.7):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None

def health_ok(port: int) -> bool:
    return get_json(f"http://{HOST}:{port}/api/health", 0.45) is not None

def compatible(port: int) -> bool:
    if not health_ok(port):
        return False
    d = get_json(f"http://{HOST}:{port}/api/ga-brain/status", 0.8)
    from app.modules.ga_brain.api_ga_brain import BUILD_VERSION
    return bool(d and d.get("build_version") == BUILD_VERSION and d.get("interact_ready") is True)

def find_compatible_running():
    for port in range(PORT_START, PORT_END + 1):
        if compatible(port):
            return port
    return None

def find_free():
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                pass
    raise RuntimeError("Không tìm thấy cổng trống 8123-8199")

def open_when_ready(port: int):
    url = f"http://{HOST}:{port}/?studio=0.8.9.3.3&ga=v9.7"
    for _ in range(300):
        if compatible(port):
            job_log_broker.publish("system", "startup", f"Backend: health OK tại cổng {port} - đang mở trình duyệt.", level="success")
            webbrowser.open(url)
            return
        time.sleep(0.2)
    job_log_broker.publish("system", "startup", f"Backend: hết thời gian chờ health OK tại cổng {port}.", level="warning")

def log_error(exc: BaseException):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(
            f"TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"TYPE: {type(exc).__name__}\n"
            f"MESSAGE: {exc}\n\n" + traceback.format_exc(),
            encoding="utf-8",
        )
    except Exception:
        pass

def main():
    os.chdir(ROOT)

    job_log_broker.publish("system", "startup", "Đang kiểm tra tiến trình AI Video Factory đang chạy...")
    active = find_compatible_running()
    if active is not None:
        job_log_broker.publish("system", "startup", f"Đã tìm thấy tiến trình đang chạy ở cổng {active} - mở lại trình duyệt.", level="success")
        webbrowser.open(f"http://{HOST}:{active}/?studio=0.8.9.3.3&ga=v9.7")
        return

    job_log_broker.publish("system", "startup", "Không có tiến trình tương thích đang chạy - đang khởi động backend mới.")
    from app.main import app

    job_log_broker.publish("system", "startup", "Backend: đã nạp app FastAPI.")
    # If old backend occupies 8123, leave it alone and use next port.
    port = find_free()
    data_dir = ROOT / "data" / "ga_maintenance"
    data_dir.mkdir(parents=True, exist_ok=True)
    MODE.write_text("GA_BRAIN_V9_7", encoding="utf-8")
    (data_dir / "active_port.txt").write_text(str(port), encoding="utf-8")
    job_log_broker.publish("system", "startup", f"Backend: đang bind cổng {port}...")

    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, reload=False, log_level="warning", access_log=False)

if __name__ == "__main__":
    try:
        with job_log_broker.capture("system", "startup"):
            main()
    except BaseException as exc:
        log_error(exc)
        try:
            job_log_broker.publish("system", "startup", f"Launcher: lỗi khởi động - {exc!r}", level="error")
            print("AI Video Factory startup error:", repr(exc))
            print("Log:", LOG)
        except Exception:
            pass
        time.sleep(30)
