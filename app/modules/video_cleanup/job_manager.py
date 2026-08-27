from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

from app.modules.video_editor.ffmpeg_tools import ffmpeg_bin
from app.modules.job_control import JobCancelled, terminate_process
from app.modules.video_editor.probe import probe_video


class VideoCleanupJobManager:
    def __init__(self, runtime, workspace, jobs_root: str | Path):
        self.runtime = runtime
        self.workspace = workspace
        self.root = Path(jobs_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._procs: dict[str, subprocess.Popen] = {}

    def _new(self, kind: str) -> tuple[str, Path]:
        job_id = uuid4().hex
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=False)
        now = time.time()
        with self._lock:
            self._cancel_events[job_id] = threading.Event()
            self._jobs[job_id] = {
                "job_id": job_id, "kind": kind, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "detail": "", "created_at": now, "updated_at": now,
                "result": None, "error": None, "log": [], "cancellable": True,
            }
        return job_id, folder

    def _update(self, job_id: str, *, progress=None, stage=None, detail=None, log=None, **extra):
        with self._lock:
            job = self._jobs[job_id]
            if progress is not None:
                p = max(0, min(100, int(progress)))
                job["progress"] = max(int(job.get("progress", 0)), p) if p else p
            if stage is not None: job["stage"] = stage
            if detail is not None: job["detail"] = detail
            if log:
                job["log"].append(str(log)[-1200:]); job["log"] = job["log"][-30:]
            job.update(extra); job["updated_at"] = time.time()

    def _consume_worker(self, job_id: str, proc: subprocess.Popen, initial_stage: str) -> tuple[int, str]:
        with self._lock:
            self._procs[job_id] = proc
        q: queue.Queue[str | None] = queue.Queue()
        def reader():
            assert proc.stdout is not None
            for line in proc.stdout:
                q.put(line.rstrip("\r\n"))
            q.put(None)
        threading.Thread(target=reader, daemon=True).start()
        started = time.time(); last_real = 0
        while True:
            if self._cancel_events[job_id].is_set():
                terminate_process(proc)
                with self._lock:
                    self._procs.pop(job_id, None)
                raise JobCancelled("Đã dừng tác vụ dọn video")
            try:
                line = q.get(timeout=1.0)
            except queue.Empty:
                line = ""
            if line is None:
                break
            if line:
                try:
                    data = json.loads(line)
                    p = int(data.get("progress", 0) or 0)
                    if p > 0:
                        last_real = max(last_real, p)
                        self._update(job_id, progress=p, stage=data.get("stage"), detail=data.get("detail"), log=line)
                    elif data.get("stage"):
                        self._update(job_id, stage=data.get("stage"), detail=data.get("detail"), log=line)
                except Exception:
                    self._update(job_id, log=line)
            elif last_real < 24:
                elapsed = int(time.time() - started)
                pseudo = min(23, 7 + elapsed // 8)
                size = self._folder_size_gb(self.runtime.model_dir)
                detail = f"{elapsed}s · model cache {size:.2f} GB · % ước tính"
                self._update(job_id, progress=pseudo, stage=initial_stage, detail=detail)
        stderr = ""
        if proc.stderr is not None:
            stderr = proc.stderr.read()
        code = proc.wait()
        with self._lock:
            self._procs.pop(job_id, None)
        return code, stderr

    @staticmethod
    def _folder_size_gb(path: Path) -> float:
        total = 0
        try:
            for p in path.rglob("*"):
                if p.is_file(): total += p.stat().st_size
        except OSError:
            pass
        return total / (1024 ** 3)

    def start_background(self, session_id: str, *, mode="transparent", color="#00ff00", model="u2net_human_seg") -> str:
        status = self.runtime.status()
        if not status.get("ready"):
            raise ValueError("Chưa cài Video Cleanup AI. Chạy SETUP_VIDEO_CLEANUP_AI.bat một lần.")
        if mode not in {"transparent", "solid"}:
            raise ValueError("Chế độ nền không hợp lệ")
        if model not in {"u2net_human_seg", "isnet-general-use"}:
            raise ValueError("Model xóa nền không hợp lệ")
        source = self.workspace.current_path(session_id)
        job_id, folder = self._new("background")
        suffix = ".webm" if mode == "transparent" else ".mp4"
        output = folder / f"background_removed{suffix}"

        def worker():
            self._update(job_id, status="running", progress=4, stage="Chuẩn bị xóa nền AI", detail="Giữ nguyên video gốc")
            env = {**os.environ, "U2NET_HOME": str(self.runtime.model_dir)}
            cmd = [str(self.runtime.python_exe), str(self.runtime.background_worker), "--input", str(source),
                   "--output", str(output), "--ffmpeg", ffmpeg_bin(), "--model", model, "--mode", mode, "--color", color]
            try:
                proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=1)
                rc, stderr = self._consume_worker(job_id, proc, "Đang tải / nạp model xóa nền")
                if rc != 0:
                    raise RuntimeError((stderr or "Xóa nền AI thất bại")[-1600:])
                info = self.workspace.add_version(session_id, output, "Xóa nền AI" + (" · trong suốt" if mode == "transparent" else ""))
                self._update(job_id, status="done", progress=100, stage="Hoàn tất", detail="Đã xóa nền và đưa vào editor", result={"editor": info})
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(job_id, status="error", stage="Lỗi xóa nền", detail=str(exc), error=str(exc))
        threading.Thread(target=worker, daemon=True, name=f"aivf-bg-{job_id[:8]}").start()
        return job_id

    def _rect_pixels(self, session_id: str, x: float, y: float, w: float, h: float, padding: int) -> tuple[Path, int, int, int, int, float]:
        source = self.workspace.current_path(session_id)
        info = probe_video(source)
        vals = [float(x), float(y), float(w), float(h)]
        if any(v < 0 or v > 1 for v in vals) or w <= 0 or h <= 0 or x + w > 1.001 or y + h > 1.001:
            raise ValueError("Vùng xóa không hợp lệ")
        px = max(0, int(round(x * info.width)) - padding)
        py = max(0, int(round(y * info.height)) - padding)
        pw = min(info.width - px, max(4, int(round(w * info.width)) + padding * 2))
        ph = min(info.height - py, max(4, int(round(h * info.height)) + padding * 2))
        return source, px, py, pw, ph, info.duration

    def start_overlay(self, session_id: str, *, x: float, y: float, w: float, h: float, padding=4, method="delogo") -> str:
        if method not in {"delogo", "inpaint"}:
            raise ValueError("Kiểu xóa vùng không hợp lệ")
        if method == "inpaint" and not self.runtime.status().get("ready"):
            raise ValueError("Inpaint cần Video Cleanup AI. Chạy SETUP_VIDEO_CLEANUP_AI.bat một lần.")
        source, px, py, pw, ph, duration = self._rect_pixels(session_id, x, y, w, h, max(0, min(80, int(padding))))
        job_id, folder = self._new("overlay")
        output = folder / "overlay_removed.mp4"

        def worker():
            self._update(job_id, status="running", progress=5, stage="Chuẩn bị vùng xóa", detail=f"{px},{py} · {pw}×{ph}")
            try:
                if method == "inpaint":
                    env = {**os.environ, "U2NET_HOME": str(self.runtime.model_dir)}
                    cmd = [str(self.runtime.python_exe), str(self.runtime.inpaint_worker), "--input", str(source), "--output", str(output),
                           "--ffmpeg", ffmpeg_bin(), "--x", str(px), "--y", str(py), "--w", str(pw), "--h", str(ph), "--radius", "5"]
                    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=1)
                    rc, stderr = self._consume_worker(job_id, proc, "Đang xóa chữ / icon")
                    if rc != 0:
                        raise RuntimeError((stderr or "Inpaint thất bại")[-1600:])
                else:
                    self._run_delogo(job_id, source, output, px, py, pw, ph, duration)
                info = self.workspace.add_version(session_id, output, "Xóa chữ / icon" + (" · inpaint" if method == "inpaint" else " · nhanh"))
                self._update(job_id, status="done", progress=100, stage="Hoàn tất", detail="Đã xóa vùng và đưa vào editor", result={"editor": info})
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(job_id, status="error", stage="Lỗi xóa vùng", detail=str(exc), error=str(exc))
        threading.Thread(target=worker, daemon=True, name=f"aivf-erase-{job_id[:8]}").start()
        return job_id

    def _run_delogo(self, job_id: str, source: Path, output: Path, x: int, y: int, w: int, h: int, duration: float) -> None:
        filt = f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"
        cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", filt,
               "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output)]
        proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)
        with self._lock:
            self._procs[job_id] = proc
        assert proc.stdout is not None
        for raw in proc.stdout:
            if self._cancel_events[job_id].is_set():
                terminate_process(proc)
                with self._lock:
                    self._procs.pop(job_id, None)
                raise JobCancelled("Đã dừng xóa chữ / icon")
            line = raw.strip()
            if line.startswith("out_time_ms="):
                try:
                    seconds = int(line.split("=", 1)[1]) / 1_000_000
                    pct = 10 + int(min(1.0, seconds / max(duration, .1)) * 82)
                    self._update(job_id, progress=pct, stage="Đang xóa chữ / icon", detail=f"{seconds:.1f}s / {duration:.1f}s · FFmpeg")
                except ValueError:
                    pass
        stderr = proc.stderr.read() if proc.stderr else ""
        code = proc.wait()
        with self._lock:
            self._procs.pop(job_id, None)
        if code != 0:
            raise RuntimeError((stderr or "FFmpeg delogo thất bại")[-1600:])
        if not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError("Không tạo được video sau khi xóa vùng")
        self._update(job_id, progress=96, stage="Đã xóa vùng", detail="Đang đưa kết quả vào editor")

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancel_events.get(job_id)
            job = self._jobs.get(job_id)
            proc = self._procs.get(job_id)
            if not event or not job or job.get("status") not in {"queued", "running", "cancelling"}:
                return False
            event.set()
            job.update(status="cancelling", stage="Đang dừng…", detail="Đang kết thúc tác vụ dọn video", updated_at=time.time())
        terminate_process(proc)
        return True

    def cancel_all(self) -> int:
        with self._lock:
            ids=[jid for jid,j in self._jobs.items() if j.get("status") in {"queued","running","cancelling"}]
        return sum(1 for jid in ids if self.cancel(jid))

    def get(self, job_id: str) -> dict:
        clean = "".join(c for c in str(job_id) if c.isalnum())
        if clean != job_id or len(clean) < 8:
            raise ValueError("Mã job không hợp lệ")
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError("Không tìm thấy job Video Cleanup")
            item = dict(self._jobs[job_id]); item["log"] = list(item.get("log") or [])
            return item
