"""Optional high-quality Hunyuan3D backend adapter; kept separate from TripoSR."""
from __future__ import annotations

from pathlib import Path


class Hunyuan3DBackend:
    """Reserved backend for stronger GPUs. It is intentionally optional in 0.8."""

    def __init__(self, tool_dir: str | Path):
        self.tool_dir = Path(tool_dir).resolve()

    def status(self) -> dict:
        ready = (self.tool_dir / "api_server.py").exists()
        return {
            "backend": "hunyuan3d",
            "installed": ready,
            "experimental": True,
            "message": "Hunyuan3D đã có source" if ready else "Chưa cài Hunyuan3D; TripoSR là backend mặc định nhẹ hơn.",
        }
