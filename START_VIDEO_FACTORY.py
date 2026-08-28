from __future__ import annotations

import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

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
    print(f"[CANH BAO] Mở thủ công: {home_url}")


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


def main() -> None:
    if is_already_running(PORT_START):
        print(f"AI Video Factory đã đang chạy tại http://{HOST}:{PORT_START} - chỉ mở lại trình duyệt.")
        webbrowser.open(f"http://{HOST}:{PORT_START}/?studio=0.8.9.0")
        return

    port = find_free_port()
    print("=" * 68)
    print(" AI VIDEO FACTORY - FREE LOCAL STUDIO 0.8")
    print(" Editor | Whisper local | Argos Translate | Stable Diffusion local")
    print(" Khong bat buoc API tra phi")
    print("=" * 68)
    print(f"Đang chạy tại http://{HOST}:{port}")
    print("Đóng cửa sổ này hoặc nhấn Ctrl+C để tắt Studio.\n")
    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    uvicorn.run("app.main:app", host=HOST, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
