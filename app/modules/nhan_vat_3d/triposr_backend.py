"""TripoSR backend with local-cache preflight and streamed stage progress."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import shutil
import threading
import time
from pathlib import Path

from app.modules.job_control import JobCancelled, terminate_process

from .texture_cuda_patch import apply_texture_cuda_patch
from .windows_path_staging import create_ascii_staging_dir, has_non_ascii
from .image_preprocess import prepare_image_for_3d


class TripoSRBackend:
    STAGES = (
        ("Initializing model finished", 30, "Nạp model xong"),
        ("Initializing model", 12, "Đang nạp TripoSR vào RAM/GPU"),
        ("Processing images finished", 43, "Xử lý ảnh xong"),
        ("Processing images", 34, "Đang tách nền / chuẩn hóa ảnh"),
        ("Running model finished", 67, "AI suy luận xong"),
        ("Running model", 48, "Đang chạy AI trên CUDA"),
        ("Rendering finished", 80, "Render preview xong"),
        ("Rendering", 70, "Đang render preview"),
        ("Extracting mesh finished", 93, "Tách mesh xong"),
        ("Extracting mesh", 82, "Đang dựng mesh 3D"),
        ("Baking texture finished", 96, "Bake texture xong"),
        ("Baking texture", 94, "Đang bake texture"),
        ("Exporting mesh and texture", 97, "Đang xuất GLB + texture"),
        ("Exporting mesh", 97, "Đang xuất GLB"),
    )

    def __init__(self, tool_dir: str | Path, model_cache: str | Path):
        self.tool_dir = Path(tool_dir).resolve()
        self.model_cache = Path(model_cache).resolve()
        self.model_cache.mkdir(parents=True, exist_ok=True)
        self.root = self.tool_dir.parents[2]
        self.runtime_dir = self.root / "data" / "runtime3d"

    @property
    def run_script(self) -> Path:
        return self.tool_dir / "run.py"

    @property
    def runtime_python(self) -> Path:
        return self.runtime_dir / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    @property
    def ready_file(self) -> Path:
        return self.runtime_dir / "READY.txt"

    @property
    def textured_glb_converter(self) -> Path:
        return self.root / "app" / "modules" / "nhan_vat_3d" / "textured_glb_export.py"

    @property
    def mesh_finisher(self) -> Path:
        return self.root / "app" / "modules" / "nhan_vat_3d" / "mesh_finish.py"

    def _finish_mesh(self, model_path: Path, *, smooth_mesh: bool, report) -> Path:
        if not self.mesh_finisher.exists():
            return model_path
        finished = model_path.with_name(model_path.stem + "_finished.glb")
        report(99, "Tối ưu mesh + dựng đứng", "Làm mượt bề mặt và căn model đứng/gọn hơn")
        cmd = [str(self.runtime_python), str(self.mesh_finisher), str(model_path), str(finished)]
        if not smooth_mesh:
            cmd.append("--no-smooth")
        done = subprocess.run(
            cmd,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if done.returncode == 0 and finished.exists():
            finished.replace(model_path)
        return model_path

    def status(self) -> dict:
        ready = self.run_script.exists() and self.runtime_python.exists() and self.ready_file.exists()
        trip = self._snapshot("stabilityai", "TripoSR", "model.ckpt")
        dino = self._snapshot("facebook", "dino-vitb16", "config.json")
        return {
            "backend": "triposr-pymcubes-progress",
            "installed": ready,
            "weights_cached": bool(trip),
            "dino_cached": bool(dino),
            "tool_dir": str(self.tool_dir),
            "runtime_python": str(self.runtime_python),
            "model_cache": str(self.model_cache),
            "message": (
                "TripoSR sẵn sàng · weights local đã có"
                if ready and trip else
                "TripoSR runtime sẵn sàng · lần đầu cần tải weights"
                if ready else
                "Chưa cài AI 3D. Chạy SETUP_FREE_3D.bat."
            ),
        }

    def _auto_device(self) -> str:
        marker = self.runtime_dir / "DEVICE.txt"
        mode = marker.read_text(encoding="utf-8").strip().lower() if marker.exists() else "cpu"
        return "cuda:0" if mode == "cuda" else "cpu"

    def _snapshot(self, org: str, repo: str, required: str) -> Path | None:
        base = self.model_cache / "hub" / f"models--{org}--{repo}" / "snapshots"
        if not base.exists():
            return None
        candidates = sorted(base.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for folder in candidates:
            if (folder / required).exists():
                return folder.resolve()
        return None

    def _patch_local_dino_support(self) -> None:
        """Teach upstream tokenizer to accept a local DINO snapshot directory."""
        path = self.tool_dir / "tsr" / "models" / "tokenizers" / "image.py"
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        if "AIVF_LOCAL_DINO_PATCH" in text:
            return
        if "import os" not in text:
            text = text.replace("from dataclasses import dataclass\n", "from dataclasses import dataclass\nimport os\n")
        old = (
            "self.model: ViTModel = ViTModel(\n"
            "            ViTModel.config_class.from_pretrained(\n"
            "                hf_hub_download(\n"
            "                    repo_id=self.cfg.pretrained_model_name_or_path,\n"
            "                    filename=\"config.json\",\n"
            "                )\n"
            "            )\n"
            "        )"
        )
        new = (
            "# AIVF_LOCAL_DINO_PATCH\n"
            "        model_ref = self.cfg.pretrained_model_name_or_path\n"
            "        if os.path.isdir(model_ref):\n"
            "            config_path = os.path.join(model_ref, \"config.json\")\n"
            "        else:\n"
            "            config_path = hf_hub_download(repo_id=model_ref, filename=\"config.json\")\n"
            "        self.model: ViTModel = ViTModel(\n"
            "            ViTModel.config_class.from_pretrained(config_path)\n"
            "        )"
        )
        if old in text:
            path.write_text(text.replace(old, new), encoding="utf-8")

    def _prepare_local_model(self) -> Path | None:
        """Use downloaded snapshots directly to avoid Hub revalidation stalls."""
        trip = self._snapshot("stabilityai", "TripoSR", "model.ckpt")
        dino = self._snapshot("facebook", "dino-vitb16", "config.json")
        if not trip or not dino:
            return None

        self._patch_local_dino_support()
        config = trip / "config.yaml"
        if config.exists():
            text = config.read_text(encoding="utf-8")
            local = dino.as_posix()
            text = re.sub(
                r'pretrained_model_name_or_path:\s*["\']?facebook/dino-vitb16["\']?',
                f'pretrained_model_name_or_path: "{local}"',
                text,
            )
            config.write_text(text, encoding="utf-8")
        return trip

    @staticmethod
    def _reader(stream, q):
        try:
            for line in iter(stream.readline, ""):
                q.put(line.rstrip())
        finally:
            q.put(None)

    def generate(self, image_path, output_dir, *, resolution=256, texture=False,
                 render_preview=False, device="auto", progress=None, timeout_seconds=1200,
                 preprocess=True, smooth_mesh=True, cancel_event=None):
        if not self.status()["installed"]:
            raise ValueError("Chưa cài AI 3D local. Chạy SETUP_FREE_3D.bat một lần.")

        def report(percent, stage, detail=""):
            if progress:
                progress(percent, stage, detail)

        image_path = Path(image_path).resolve()
        if not image_path.exists():
            raise ValueError("Ảnh đầu vào không tồn tại")
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if preprocess:
            report(14, "Tối ưu ảnh đầu vào", "Canh giữa nhân vật/vật thể, cắt gọn và dọn nền đơn giản")
            prepared = output_dir / "prepared_input.png"
            image_path = prepare_image_for_3d(image_path, prepared)
            report(18, "Ảnh đầu vào đã tối ưu", str(image_path))
        run_output_dir = output_dir
        staging_root = None
        if texture and os.name == "nt" and has_non_ascii(output_dir):
            staging_root = create_ascii_staging_dir()
            run_output_dir = staging_root / "out"
            run_output_dir.mkdir(parents=True, exist_ok=True)
            report(
                4,
                "Chuẩn bị đường dẫn Windows",
                "Project có ký tự Unicode; texture sẽ export ở thư mục tạm ASCII rồi copy về.",
            )
        resolution = max(128, min(512, int(resolution)))
        device_value = self._auto_device() if device == "auto" else ("cuda:0" if device == "cuda" else "cpu")

        report(5, "Kiểm tra cache model")
        local_model = self._prepare_local_model()
        report(
            8,
            "Weights local đã sẵn sàng" if local_model else "Chuẩn bị tải weights lần đầu",
            str(local_model or "stabilityai/TripoSR"),
        )

        save_format = "obj" if texture else "glb"
        cmd = [
            str(self.runtime_python), "-u", str(self.run_script), str(image_path),
            "--output-dir", str(run_output_dir),
            "--model-save-format", save_format,
            "--mc-resolution", str(resolution),
            "--device", device_value,
        ]
        if local_model:
            cmd.extend(["--pretrained-model-name-or-path", str(local_model)])
        if render_preview:
            cmd.append("--render")
        if texture:
            patch_result = apply_texture_cuda_patch(self.tool_dir)
            if not patch_result.get("ok"):
                raise RuntimeError(
                    "Không vá được texture CUDA: "
                    + patch_result.get("message", "không rõ lỗi")
                )
            report(
                93,
                "Chuẩn bị texture CUDA",
                patch_result.get("message", "Texture CUDA patch OK"),
            )
            cmd.extend(["--bake-texture", "--texture-resolution", "2048"])

        env = dict(os.environ)
        env["HF_HOME"] = str(self.model_cache)
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        if local_model:
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"

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
        lines = []
        eof = False
        current_stage = "Khởi động TripoSR"
        current_progress = 10
        report(current_progress, current_stage, f"device={device_value}")

        while True:
            if cancel_event is not None and cancel_event.is_set():
                terminate_process(proc)
                raise JobCancelled("Đã dừng TripoSR theo yêu cầu")
            if time.monotonic() - started > timeout_seconds:
                proc.kill()
                raise RuntimeError(
                    f"AI 3D quá thời gian {timeout_seconds // 60} phút ở bước: {current_stage}. "
                    "Log cuối:\n" + "\n".join(lines[-25:])
                )
            try:
                item = q.get(timeout=0.5)
            except queue.Empty:
                item = "__NO_LINE__"

            if item is None:
                eof = True
            elif item != "__NO_LINE__":
                lines.append(item)
                lines = lines[-120:]
                for needle, percent, stage in self.STAGES:
                    if needle in item:
                        current_progress = max(current_progress, percent)
                        current_stage = stage
                        report(current_progress, current_stage, item[-500:])
                        break

            code = proc.poll()
            if code is not None and eof:
                break

        if proc.returncode:
            raise RuntimeError("TripoSR chạy lỗi:\n" + "\n".join(lines[-40:]))

        result_dir = run_output_dir / "0"
        preview = result_dir / "render.mp4"
        model = result_dir / "mesh.glb"

        if texture:
            raw_obj = result_dir / "mesh.obj"
            texture_png = result_dir / "texture.png"
            if not raw_obj.exists() or not texture_png.exists():
                raise RuntimeError(
                    "TripoSR bake xong nhưng thiếu mesh.obj hoặc texture.png.\n"
                    + "\n".join(lines[-30:])
                )
            if not self.textured_glb_converter.exists():
                raise RuntimeError("Thiếu module đóng gói textured GLB")
            report(98, "Đóng gói GLB có màu", "Nhúng UV + texture PNG vào GLB")
            pack = subprocess.run(
                [
                    str(self.runtime_python),
                    str(self.textured_glb_converter),
                    str(raw_obj),
                    str(texture_png),
                    str(model),
                ],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if pack.returncode != 0:
                raise RuntimeError(
                    "Đóng gói GLB có màu lỗi:\n"
                    + (pack.stderr or pack.stdout or "")[-5000:]
                )
        elif not model.exists():
            candidates = list(result_dir.glob("mesh.*")) if result_dir.exists() else []
            if candidates:
                model = candidates[0]
            else:
                raise RuntimeError("TripoSR kết thúc nhưng không tạo mesh.\n" + "\n".join(lines[-30:]))

        if not model.exists():
            raise RuntimeError("Không tìm thấy GLB cuối sau khi xử lý")

        model = self._finish_mesh(model, smooth_mesh=smooth_mesh, report=report)

        if staging_root is not None:
            final_dir = output_dir / "0"
            final_dir.mkdir(parents=True, exist_ok=True)
            final_model = final_dir / "mesh.glb"
            shutil.copy2(model, final_model)
            if (result_dir / "texture.png").exists():
                shutil.copy2(result_dir / "texture.png", final_dir / "texture.png")
            if preview.exists():
                final_preview = final_dir / "render.mp4"
                shutil.copy2(preview, final_preview)
                preview = final_preview
            model = final_model
            shutil.rmtree(staging_root, ignore_errors=True)

        report(100, "Hoàn tất", "Đã tạo GLB" + (" có texture màu" if texture else ""))
        return {
            "model_path": model,
            "preview_path": preview if preview.exists() else None,
            "stdout": "\n".join(lines[-40:]),
            "device": device_value,
            "backend": "triposr-pymcubes-progress",
        }
