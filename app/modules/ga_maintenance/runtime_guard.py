from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path


class RuntimeIncidentStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.path = self.root / "data" / "ga_maintenance" / "incidents.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def record(self, source: str, exc: BaseException, extra: dict | None = None):
        item = {
            "id": time.time_ns(),
            "time": time.time(),
            "source": source,
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-24000:],
            "extra": extra or {},
        }
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def after(self, after_id: int = 0, limit: int = 20):
        if not self.path.is_file():
            return []
        out = []
        with self.lock:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        for line in lines:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if int(item.get("id") or 0) > int(after_id or 0):
                out.append(item)
        return out[-max(1, min(int(limit), 100)):]


def install_runtime_guard(app, root: str | Path):
    root = Path(root).resolve()
    store = RuntimeIncidentStore(root)
    app.state.ga_runtime_incidents = store

    @app.middleware("http")
    async def ga_runtime_exception_guard(request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            store.record("fastapi", exc, {"path": str(request.url.path), "method": request.method})
            raise

    if not getattr(threading, "_ga_guard_installed", False):
        old_thread_hook = threading.excepthook
        def thread_hook(args):
            try:
                store.record("thread", args.exc_value, {"thread": getattr(args.thread, "name", "")})
            finally:
                old_thread_hook(args)
        threading.excepthook = thread_hook
        threading._ga_guard_installed = True

    old_sys_hook = sys.excepthook
    if not getattr(sys, "_ga_guard_installed", False):
        def sys_hook(tp, value, tb):
            try:
                store.record("sys", value, {})
            finally:
                old_sys_hook(tp, value, tb)
        sys.excepthook = sys_hook
        sys._ga_guard_installed = True

    def make_lkg():
        try:
            from .self_heal import LastKnownGood
            LastKnownGood(root).ensure()
        except Exception as exc:
            store.record("lkg_init", exc, {})

    @app.on_event("startup")
    async def ga_prepare_last_known_good():
        threading.Thread(target=make_lkg, daemon=True, name="ga-lkg-snapshot").start()

    return store
