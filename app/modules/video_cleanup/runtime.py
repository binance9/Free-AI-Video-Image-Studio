from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


class VideoCleanupRuntime:
    """Describe the optional isolated rembg/OpenCV runtime."""

    def __init__(self, base_dir: str | Path, runtime_dir: str | Path, model_dir: str | Path):
        self.base_dir = Path(base_dir).resolve()
        self.runtime_dir = Path(runtime_dir).resolve()
        self.model_dir = Path(model_dir).resolve()
        self.model_dir.mkdir(parents=True, exist_ok=True)

    @property
    def python_exe(self) -> Path:
        if os.name == "nt":
            return self.runtime_dir / "venv" / "Scripts" / "python.exe"
        return self.runtime_dir / "venv" / "bin" / "python"

    @property
    def background_worker(self) -> Path:
        return self.base_dir / "app" / "modules" / "video_cleanup" / "background_worker.py"

    @property
    def inpaint_worker(self) -> Path:
        return self.base_dir / "app" / "modules" / "video_cleanup" / "inpaint_worker.py"

    def status(self) -> dict:
        payload = {
            "ready": False,
            "python": str(self.python_exe),
            "runtime_dir": str(self.runtime_dir),
            "model_dir": str(self.model_dir),
            "providers": [],
            "gpu": False,
            "detail": "Chưa cài Video Cleanup AI",
        }
        if not self.python_exe.is_file():
            return payload
        code = (
            "import json,cv2,rembg,onnxruntime as ort; "
            "p=ort.get_available_providers(); "
            "print(json.dumps({'providers':p,'gpu':'CUDAExecutionProvider' in p,'cv2':cv2.__version__}))"
        )
        try:
            proc = subprocess.run(
                [str(self.python_exe), "-c", code],
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
                env={**os.environ, "U2NET_HOME": str(self.model_dir)},
            )
            if proc.returncode != 0:
                payload["detail"] = (proc.stderr or proc.stdout or "Runtime cleanup lỗi").strip()[-600:]
                return payload
            data = json.loads((proc.stdout or "{}").strip().splitlines()[-1])
            payload.update({
                "ready": True,
                "providers": data.get("providers", []),
                "gpu": bool(data.get("gpu")),
                "detail": "Video Cleanup AI sẵn sàng" + (" · CUDA" if data.get("gpu") else " · CPU"),
            })
            return payload
        except Exception as exc:
            payload["detail"] = f"Không kiểm tra được runtime cleanup: {exc}"
            return payload
