from __future__ import annotations

import socket
import os
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

# pythonw.exe has no console handles. Give libraries valid sinks while the
# per-job broker still forwards bound stdout/stderr into web SSE.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

HOST = "127.0.0.1"
PORT_START = 8123
PORT_END = 8199


def find_free_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("Không tìm thấy cổng trống từ 8123 đến 8199")


def open_when_ready(port: int) -> None:
    health_url = f"http://{HOST}:{port}/api/health"
    home_url = f"http://{HOST}:{port}/?studio=0.8.9.0"
    for _ in range(120):
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(home_url)
                    return
        except Exception:
            time.sleep(0.25)
    return


def is_already_running(port: int) -> bool:
    """Bot ON: server that su dang lang nghe tren cong chinh (8123) va tra
    loi /api/health hop le. Dung de bao dam KHONG BAO GIO chay 2 instance
    cung luc - neu server da song, launcher chi mo lai web, khong spawn
    tien trinh moi."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=0.6) as response:
            return response.status == 200
    except Exception:
        return False


def running_port() -> int | None:
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.03)
            listening = probe.connect_ex((HOST, port)) == 0
        if listening and is_already_running(port):
            return port
    return None


def main() -> None:
    active_port = PORT_START if is_already_running(PORT_START) else running_port()
    if active_port is not None:
        webbrowser.open(f"http://{HOST}:{active_port}/?studio=0.8.9.3")
        return

    port = find_free_port()
    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    uvicorn.run("app.main:app", host=HOST, port=port, reload=False, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
