"""Optional Character HD backend using Tencent Hunyuan3D-2mini in an isolated venv."""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from app.core.shared_services import JobCancelled, terminate_process


class CharacterHDBackend:
    def __init__(self, root: str | Path, model_cache: str | Path):
        self.root = Path(root).resolve()
        self.model_cache = Path(model_cache).resolve()
        self.runtime_dir = self.root / "data" / "runtime_character_hd"
        self.tool_dir = self.root / "tools" / "external" / "Hunyuan3D-2"
        self.runner = self.root / "app" / "modules" / "nhan_vat_3d" / "run_character_hd.py"

    @property
    def python(self) -> Path:
        return self.runtime_dir / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    @property
    def ready_file(self) -> Path:
        return self.runtime_dir / "READY.txt"

    @property
    def texture_ready_file(self) -> Path:
        return self.runtime_dir / "TEXTURE_READY.txt"

    def status(self) -> dict:
        installed = self.python.exists() and self.ready_file.exists() and self.tool_dir.exists()
        texture_ready = installed and self.texture_ready_file.exists()
        return {
            "backend": "character-hd-hunyuan3d2mini",
            "installed": installed,
            "texture_ready": texture_ready,
            "tool_dir": str(self.tool_dir),
            "runtime_python": str(self.python),
            "message": (
                "Character HD sẵn sàng" if installed
                else "Chưa cài Character HD · chạy SETUP_CHARACTER_HD.bat một lần"
            ),
            "texture_message": (
                "Paint native sẵn sàng · có thể tô màu GLB hiện có" if texture_ready
                else "Paint native chưa sẵn sàng · chạy SETUP_CHARACTER_HD_TEXTURE.bat"
            ),
        }

    @staticmethod
    def _reader(stream, q):
        try:
            for line in iter(stream.readline, ""):
                q.put(line.rstrip())
        finally:
            q.put(None)

    def paint_existing(self, mesh_path: str | Path, image_path: str | Path, output_dir: str | Path, *,
                       progress=None, timeout_seconds=14400, idle_timeout_seconds=1800, cancel_event=None) -> dict:
        status = self.status()
        if not status["installed"]:
            raise ValueError("Character HD chưa cài. Chạy SETUP_CHARACTER_HD.bat trước.")
        if not status.get("texture_ready"):
            raise ValueError(
                "Paint native chưa sẵn sàng. Chạy SETUP_CHARACTER_HD_TEXTURE.bat một lần; "
                "mesh trắng hiện tại vẫn được giữ nguyên."
            )

        mesh_path = Path(mesh_path).resolve()
        image_path = Path(image_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "character_hd_colored.glb"
        paint_runner = self.root / "app" / "modules" / "nhan_vat_3d" / "run_character_hd_paint.py"
        cmd = [str(self.python), "-u", str(paint_runner), str(mesh_path), str(image_path), str(output_path)]

        env = dict(os.environ)
        env["HF_HOME"] = str(self.model_cache)
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTORCH_CUDA_ALLOC_CONF"] = env.get("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        env["PYTHONPATH"] = str(self.tool_dir) + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            cmd, cwd=str(self.tool_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        q = queue.Queue()
        threading.Thread(target=self._reader, args=(proc.stdout, q), daemon=True).start()
        started = time.monotonic()
        last_worker_activity = started
        current_pct = 0
        current_stage = "Khởi động Paint"
        lines = []
        eof = False
        texture_applied = False
        texture_size = None
        if progress:
            progress(5, "Khởi động Paint HD", "Giữ nguyên shape · chỉ tô màu model hiện có")

        while True:
            if cancel_event is not None and cancel_event.is_set():
                terminate_process(proc)
                raise JobCancelled("Đã dừng Paint HD theo yêu cầu")
            now = time.monotonic()
            if now - started > timeout_seconds:
                proc.kill()
                raise RuntimeError("Paint HD quá thời gian tối đa 4 giờ. Mesh trắng gốc vẫn còn nguyên.")
            if now - last_worker_activity > idle_timeout_seconds and proc.poll() is None:
                proc.kill()
                raise RuntimeError(
                    f"Paint HD không có heartbeat trong 30 phút ở bước {current_pct}% - {current_stage}. "
                    "Mesh trắng gốc vẫn còn nguyên."
                )
            try:
                item = q.get(timeout=0.5)
            except queue.Empty:
                item = "__NO_LINE__"
            if item is None:
                eof = True
            elif item != "__NO_LINE__":
                last_worker_activity = time.monotonic()
                lines.append(item)
                lines = lines[-100:]
                if item.startswith("AIVF_TEXTURE_APPLIED|"):
                    texture_applied = item.endswith("|1")
                elif item.startswith("AIVF_TEXTURE_SIZE|"):
                    try:
                        texture_size = int(item.split("|", 1)[1])
                    except Exception:
                        texture_size = None
                elif item.startswith("AIVF_PROGRESS|"):
                    parts = item.split("|", 3)
                    if len(parts) >= 3:
                        try:
                            pct = int(parts[1])
                        except ValueError:
                            pct = 10
                        stage = parts[2]
                        detail = parts[3] if len(parts) > 3 else ""
                        current_pct, current_stage = pct, stage
                        if progress:
                            progress(pct, stage, detail)
            if proc.poll() is not None and eof:
                break

        if proc.returncode:
            raise RuntimeError("Paint HD chạy lỗi:\n" + "\n".join(lines[-35:]))
        if not output_path.exists() or not texture_applied:
            raise RuntimeError("Paint HD kết thúc nhưng GLB chưa có texture màu hợp lệ. Mesh trắng gốc vẫn còn nguyên.")
        return {
            "model_path": output_path,
            "preview_path": None,
            "stdout": "\n".join(lines[-35:]),
            "device": "cuda:low-vram-offload",
            "backend": "character-hd-hunyuan3d-paint",
            "texture_applied": True,
            "texture_size": texture_size,
            "mesh_profile": "existing",
        }

    def generate(self, image_path: str | Path, output_dir: str | Path, *, texture=False,
                 optimize_mesh=True, mesh_profile="hd", progress=None, timeout_seconds=14400, idle_timeout_seconds=1800, cancel_event=None) -> dict:
        if not self.status()["installed"]:
            raise ValueError("Character HD chưa cài. Chạy SETUP_CHARACTER_HD.bat một lần rồi mở lại app.")

        image_path = Path(image_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = output_dir / "character_hd.glb"

        cmd = [str(self.python), "-u", str(self.runner), str(image_path), str(model_path)]
        if texture:
            cmd.append("--texture")
        if optimize_mesh:
            cmd.append("--optimize-light")
            profile = str(mesh_profile or "hd").strip().lower()
            if profile not in {"hd", "medium", "light"}:
                profile = "hd"
            cmd.extend(["--mesh-profile", profile])
        else:
            profile = "original"

        env = dict(os.environ)
        env["HF_HOME"] = str(self.model_cache)
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        # Make the cloned repository importable without installing into main Python.
        env["PYTHONPATH"] = str(self.tool_dir) + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.Popen(
            cmd,
            cwd=str(self.tool_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        q = queue.Queue()
        threading.Thread(target=self._reader, args=(proc.stdout, q), daemon=True).start()
        started = time.monotonic()
        last_worker_activity = started
        last_cache_gb = -1.0
        current_pct = 0
        current_stage = "Khởi động"
        lines = []
        eof = False
        texture_applied = False
        faces_before = 0
        faces_after = 0
        mesh_profile_used = profile
        if progress:
            progress(5, "Khởi động Character HD", "Hunyuan3D-2mini")

        while True:
            if cancel_event is not None and cancel_event.is_set():
                terminate_process(proc)
                raise JobCancelled("Đã dừng Character HD theo yêu cầu")
            now = time.monotonic()
            if now - started > timeout_seconds:
                proc.kill()
                raise RuntimeError(
                    "Character HD quá thời gian tối đa 4 giờ. Cache/model có thể đã tải một phần; "
                    "mở lại app rồi chạy tiếp để dùng cache hiện có."
                )
            # 0.8.6.3: never use cache growth as a proxy for inference progress.
            # Once weights are downloaded the cache naturally stops growing while CUDA may
            # spend a long time inside shape generation.  The worker emits heartbeats for
            # long silent stages; only kill when the worker itself has been silent for 30m.
            if now - last_worker_activity > idle_timeout_seconds and proc.poll() is None:
                proc.kill()
                raise RuntimeError(
                    f"Character HD không có heartbeat trong 30 phút ở bước {current_pct}% - {current_stage}. "
                    "Cache/model đã tải vẫn được giữ lại; mở lại app rồi thử tiếp."
                )
            try:
                item = q.get(timeout=0.5)
            except queue.Empty:
                item = "__NO_LINE__"

            if item is None:
                eof = True
            elif item != "__NO_LINE__":
                last_worker_activity = time.monotonic()
                lines.append(item)
                lines = lines[-100:]
                if item.startswith("AIVF_TEXTURE_APPLIED|"):
                    texture_applied = item.endswith("|1")
                elif item.startswith("AIVF_MESH_OPTIMIZED|"):
                    parts = item.split("|")
                    if len(parts) >= 3:
                        try:
                            faces_before = int(parts[1])
                            faces_after = int(parts[2])
                        except ValueError:
                            pass
                    if len(parts) >= 4 and parts[3] in {"hd", "medium", "light"}:
                        mesh_profile_used = parts[3]
                elif item.startswith("AIVF_PROGRESS|"):
                    parts = item.split("|", 3)
                    if len(parts) >= 3:
                        try:
                            pct = int(parts[1])
                        except ValueError:
                            pct = 10
                        stage = parts[2]
                        detail = parts[3] if len(parts) > 3 else ""
                        current_pct = pct
                        current_stage = stage
                        if "cache Character HD" in detail:
                            import re
                            match = re.search(r"cache Character HD\s+([0-9]+(?:\.[0-9]+)?)\s+GB", detail)
                            if match:
                                try:
                                    cache_gb = float(match.group(1))
                                    if cache_gb > last_cache_gb + 0.001:
                                        last_cache_gb = cache_gb
                                except ValueError:
                                    pass
                        if progress:
                            progress(pct, stage, detail)

            if proc.poll() is not None and eof:
                break

        if proc.returncode:
            raise RuntimeError("Character HD chạy lỗi:\n" + "\n".join(lines[-35:]))
        if not model_path.exists():
            raise RuntimeError("Character HD kết thúc nhưng không có GLB")

        return {
            "model_path": model_path,
            "preview_path": None,
            "stdout": "\n".join(lines[-35:]),
            "device": "cuda:auto",
            "backend": "character-hd-hunyuan3d2mini",
            "texture_applied": texture_applied,
            "mesh_optimized": bool(faces_before and faces_after and faces_after < faces_before),
            "faces_before": faces_before or None,
            "faces_after": faces_after or None,
            "mesh_profile": mesh_profile_used,
        }
