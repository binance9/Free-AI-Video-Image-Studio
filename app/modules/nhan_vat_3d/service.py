"""Orchestrate prompt/image to 3D while keeping each model backend isolated."""
from __future__ import annotations

from pathlib import Path
import inspect
from PIL import Image

from .triposr_backend import TripoSRBackend
from .character_hd_backend import CharacterHDBackend


class Local3DService:
    def __init__(self, triposr_dir: str | Path, model_cache: str | Path, image_service=None,
                 root: str | Path | None = None):
        self.triposr = TripoSRBackend(triposr_dir, model_cache)
        self.root = Path(root).resolve() if root else self.triposr.root
        self.character_hd = CharacterHDBackend(self.root, Path(model_cache).resolve() / "character_hd")
        self.image_service = image_service

    def status(self) -> dict:
        quick = self.triposr.status()
        hd = self.character_hd.status()
        return {
            **quick,
            "backends": {
                "quick": quick,
                "character_hd": hd,
            },
            "character_hd_installed": hd["installed"],
            "character_hd_message": hd["message"],
        }

    def from_image(self, image_path: str | Path, work_dir: str | Path, *, resolution: int = 256,
                   texture: bool = False, render_preview: bool = False, progress=None,
                   backend: str = "quick", optimize_mesh: bool = True, mesh_profile: str = "hd", cancel_event=None) -> dict:
        self._validate_image(image_path)
        backend = (backend or "quick").strip().lower()
        if backend == "character_hd":
            return self.character_hd.generate(
                image_path,
                work_dir,
                texture=texture,
                optimize_mesh=optimize_mesh,
                mesh_profile=mesh_profile,
                progress=progress,
                cancel_event=cancel_event,
            )
        result = self.triposr.generate(
            image_path, work_dir, resolution=resolution,
            texture=texture, render_preview=render_preview, progress=progress, cancel_event=cancel_event,
        )
        # The HD mesh profiles apply only to Character HD; avoid displaying an
        # HD/Medium/Light badge on TripoSR results.
        result["mesh_profile"] = "original"
        return result

    def colorize_existing(self, mesh_path: str | Path, image_path: str | Path, work_dir: str | Path, *, progress=None, cancel_event=None) -> dict:
        self._validate_image(image_path)
        mesh_path = Path(mesh_path)
        if not mesh_path.exists() or mesh_path.suffix.lower() != ".glb":
            raise ValueError("Model để tô màu phải là file GLB hợp lệ")
        return self.character_hd.paint_existing(mesh_path, image_path, work_dir, progress=progress, cancel_event=cancel_event)

    def from_prompt(self, prompt: str, work_dir: str | Path, *, style: str = "cartoon3d",
                    resolution: int = 256, texture: bool = False,
                    render_preview: bool = False, progress=None,
                    backend: str = "quick", optimize_mesh: bool = True, mesh_profile: str = "hd", cancel_event=None) -> dict:
        if self.image_service is None:
            raise ValueError("AI ảnh local chưa được nối với AI 3D")
        prompt = (prompt or "").strip()
        if len(prompt) < 3:
            raise ValueError("Mô tả nhân vật/vật thể quá ngắn")
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        image_kwargs = {"style": style, "size": "1024x1024", "quality": "high"}
        try:
            if "cancel_event" in inspect.signature(self.image_service.generate).parameters:
                image_kwargs["cancel_event"] = cancel_event
        except Exception:
            pass
        concept = self.image_service.generate(
            prompt + ", single full body character or isolated object, centered, neutral standing pose if character, front or slight three-quarter view, plain background, full silhouette visible, no text",
            **image_kwargs,
        )
        concept_path = work_dir / "concept.png"
        concept_path.write_bytes(concept)
        if progress:
            progress(1, "Concept đã xong", "Đang chuyển concept sang backend 3D")
        result = self.from_image(
            concept_path,
            work_dir / ("character_hd" if backend == "character_hd" else "triposr"),
            resolution=resolution,
            texture=texture,
            render_preview=render_preview,
            progress=progress,
            backend=backend,
            optimize_mesh=optimize_mesh,
            mesh_profile=mesh_profile,
            cancel_event=cancel_event,
        )
        result["concept_path"] = concept_path
        return result

    @staticmethod
    def _validate_image(path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise ValueError("Ảnh tham chiếu không tồn tại")
        try:
            with Image.open(path) as im:
                if im.width < 128 or im.height < 128:
                    raise ValueError("Ảnh tham chiếu quá nhỏ; nên dùng tối thiểu 512×512")
                im.verify()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Ảnh tham chiếu không đọc được") from exc
