from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT_START = 8123
PORT_END = 8199

DATA_DIR = ROOT / "data" / "ga_maintenance"
LOG = DATA_DIR / "desktop_launcher.log"
FINGERPRINT_FILE = DATA_DIR / "desktop_source_fingerprint.json"
RESTART_MARKER = DATA_DIR / "restart.request"
RESTART_PENDING = DATA_DIR / "desktop_restart_pending.json"

SOURCE_EXTENSIONS = {".py", ".js", ".css", ".html", ".json"}
SOURCE_ROOTS = ("app", "web")
EXCLUDED_PARTS = {
    "__pycache__", ".git", ".idea", ".vscode", "node_modules",
    "models", "data", "_verify_model_cache",
}


def _log(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    try:
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass


def _iter_source_files(root: Path = ROOT):
    for folder_name in SOURCE_ROOTS:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            rel_parts = path.relative_to(root).parts
            if any(part in EXCLUDED_PARTS or part.startswith("_BACKUP_") for part in rel_parts):
                continue
            yield path


def source_fingerprint(root: Path = ROOT) -> dict:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(_iter_source_files(root), key=lambda p: p.as_posix().lower()):
        rel = path.relative_to(root).as_posix().encode("utf-8", "replace")
        digest.update(rel)
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while True:
                    block = handle.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
        except OSError:
            continue
        digest.update(b"\0")
        count += 1
    return {"sha256": digest.hexdigest(), "file_count": count}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def needs_refresh(last: dict, current: dict, *, restart_requested: bool = False) -> bool:
    return bool(
        restart_requested
        or not last
        or last.get("sha256") != current.get("sha256")
        or int(last.get("file_count") or 0) != int(current.get("file_count") or 0)
    )


def _get_json(url: str, timeout: float = 0.8) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            value = json.loads(response.read().decode("utf-8", "replace"))
            return value if isinstance(value, dict) else None
    except Exception:
        return None


def _post_json(url: str, timeout: float = 1.0) -> dict | None:
    try:
        req = urllib.request.Request(url, data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", "replace"))
            return value if isinstance(value, dict) else None
    except Exception:
        return None


def health_ok(port: int) -> bool:
    value = _get_json(f"http://{HOST}:{port}/api/health", 0.45)
    return bool(value and value.get("status") == "ok")


def is_aivf_server(port: int) -> bool:
    if not health_ok(port):
        return False
    folders = _get_json(f"http://{HOST}:{port}/api/system/folders", 0.6)
    return bool(folders and isinstance(folders.get("items"), dict))


def find_running_backend() -> int | None:
    for port in range(PORT_START, PORT_END + 1):
        if is_aivf_server(port):
            return port
    return None


def backend_busy(port: int) -> bool:
    value = _get_json(f"http://{HOST}:{port}/api/jobs/status", 0.8)
    return bool(value and value.get("busy"))


def _wait_port_down(port: int, timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not health_ok(port):
            return True
        time.sleep(0.2)
    return not health_ok(port)


def shutdown_backend(port: int) -> bool:
    _log(f"Requesting safe backend shutdown on port {port}.")
    result = _post_json(f"http://{HOST}:{port}/api/system/shutdown", 1.5)
    if not result:
        return False
    return _wait_port_down(port)


def find_free_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("Không tìm thấy cổng trống 8123-8199")


def clear_python_cache(root: Path = ROOT) -> int:
    removed = 0
    app_dir = root / "app"
    if not app_dir.is_dir():
        return 0
    for cache in list(app_dir.rglob("__pycache__")):
        try:
            shutil.rmtree(cache)
            removed += 1
        except OSError:
            pass
    return removed


def start_backend(port: int) -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = (DATA_DIR / "desktop_backend.log").open("a", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", HOST, "--port", str(port),
        "--log-level", "warning", "--no-access-log",
    ]
    kwargs = {
        "cwd": str(ROOT),
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(cmd, **kwargs)
    proc._aivf_log_handle = log_handle  # type: ignore[attr-defined]
    return proc


def wait_ready(port: int, process: subprocess.Popen | None, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_aivf_server(port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"Backend đã thoát sớm với mã {process.returncode}. Xem {DATA_DIR / 'desktop_backend.log'}")
        time.sleep(0.25)
    raise RuntimeError(f"Backend không sẵn sàng sau {int(timeout)} giây. Xem {DATA_DIR / 'desktop_backend.log'}")


def _find_edge() -> Path | None:
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def open_desktop_window(url: str) -> str:
    try:
        import webview  # optional dependency
        webview.create_window(
            "AI Video Factory",
            url,
            width=1500,
            height=940,
            min_size=(1050, 700),
        )
        webview.start()
        return "pywebview"
    except Exception as exc:
        _log(f"PyWebView unavailable/failure: {exc!r}; using Edge App Mode.")

    edge = _find_edge()
    if edge is not None:
        profile = DATA_DIR / "edge_app_profile"
        profile.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([
            str(edge),
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--new-window",
        ])
        try:
            proc.wait()
        except Exception:
            pass
        return "edge-app"

    webbrowser.open(url)
    return "browser-fallback"


def main() -> None:
    os.chdir(ROOT)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    current = source_fingerprint()
    last = _read_json(FINGERPRINT_FILE)
    restart_requested = RESTART_MARKER.is_file()
    refresh = needs_refresh(last, current, restart_requested=restart_requested)

    _log(
        "Startup | source="
        f"{current.get('sha256', '')[:12]} files={current.get('file_count')} "
        f"changed={refresh} restart_marker={restart_requested}"
    )

    active = find_running_backend()
    owned_backend = False
    process = None

    if active is not None and refresh:
        if backend_busy(active):
            _write_json_atomic(RESTART_PENDING, {
                "reason": "source_changed_but_jobs_active",
                "port": active,
                "fingerprint": current,
                "at": time.time(),
            })
            _log(f"Source changed but jobs are active on {active}; restart deferred.")
        else:
            if shutdown_backend(active):
                _log(f"Old backend {active} stopped; loading edited source.")
                active = None
            else:
                raise RuntimeError(f"Không thể dừng backend cũ ở cổng {active}")

    if active is None:
        removed = clear_python_cache(ROOT) if refresh else 0
        if removed:
            _log(f"Cleared {removed} Python __pycache__ folders.")
        port = find_free_port()
        process = start_backend(port)
        owned_backend = True
        wait_ready(port, process)
        active = port
        _write_json_atomic(FINGERPRINT_FILE, {
            **current,
            "loaded_at": time.time(),
            "port": active,
        })
        RESTART_MARKER.unlink(missing_ok=True)
        RESTART_PENDING.unlink(missing_ok=True)
        _log(f"Fresh backend ready on {active}.")

    url = (
        f"http://{HOST}:{active}/"
        f"?desktop=1&fresh={current.get('sha256', '')[:16]}&t={int(time.time())}"
    )
    shell = open_desktop_window(url)
    _log(f"Desktop shell closed: {shell}")

    if owned_backend and active is not None:
        if backend_busy(active):
            _log("Desktop window closed while jobs are active; backend left running.")
        else:
            shutdown_backend(active)
            _log("Desktop backend stopped cleanly.")


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        _log(f"FATAL: {type(exc).__name__}: {exc}")
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"AI Video Factory không khởi động được:\n\n{exc}\n\nLog:\n{LOG}",
                    "AI Video Factory",
                    0x10,
                )
            except Exception:
                pass
        else:
            raise
