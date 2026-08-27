from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class GameReady3DService:
    """Turn a static GLB into a lighter skinned/animated GLB using Blender headless."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.script = Path(__file__).with_name("blender_game_ready.py").resolve()

    def find_blender(self) -> Path | None:
        env = os.environ.get("AIVF_BLENDER") or os.environ.get("BLENDER_PATH")
        candidates: list[Path] = []
        if env:
            candidates.append(Path(env))
        which = shutil.which("blender")
        if which:
            candidates.append(Path(which))
        if os.name == "nt":
            pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            roots = [pf / "Blender Foundation"]
            for root in roots:
                if root.exists():
                    for exe in sorted(root.glob("Blender */blender.exe"), reverse=True):
                        candidates.append(exe)
            local = Path(os.environ.get("LOCALAPPDATA", ""))
            if local:
                candidates.extend(sorted(local.glob(r"Programs\Blender Foundation\Blender *\blender.exe"), reverse=True))
        for p in candidates:
            try:
                if p.exists() and p.is_file():
                    return p.resolve()
            except OSError:
                continue
        return None

    def status(self) -> dict:
        blender = self.find_blender()
        return {
            "ok": True,
            "version": "0.8.9.3",
            "installed": bool(blender),
            "blender": str(blender) if blender else None,
            "message": "Blender headless sẵn sàng" if blender else "Chưa tìm thấy Blender 4.x. Chạy SETUP_GAME_READY_3D.bat một lần.",
            "pipeline": ["optimize", "rig", "skin", "idle", "run", "attack_01", "export_glb"],
        }

    def convert(self, source: str | Path, output_dir: str | Path, *, target_faces: int = 45000) -> dict:
        source = Path(source).resolve()
        if source.suffix.lower() != ".glb" or not source.exists():
            raise ValueError("Model nguồn phải là file GLB hợp lệ")
        blender = self.find_blender()
        if not blender:
            raise RuntimeError("Chưa có Blender. Chạy SETUP_GAME_READY_3D.bat rồi mở lại bot.")
        target_faces = max(18000, min(80000, int(target_faces)))
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = out_dir / "game_ready.glb"
        report = out_dir / "game_ready_report.json"
        cmd = [
            str(blender), "--background", "--factory-startup",
            "--python", str(self.script), "--",
            "--input", str(source), "--output", str(out_glb),
            "--report", str(report), "--target-faces", str(target_faces),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
        if proc.returncode != 0 or not out_glb.exists():
            tail = "\n".join((proc.stderr or proc.stdout or "Blender xử lý thất bại").splitlines()[-16:])
            raise RuntimeError(f"Game Ready lỗi: {tail}")
        data = {}
        if report.exists():
            try:
                data = json.loads(report.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data.update({"model_path": str(out_glb), "target_faces": target_faces})
        return data
