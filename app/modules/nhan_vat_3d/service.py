"""Orchestrate prompt/image to 3D while keeping each model backend isolated."""
from __future__ import annotations

from pathlib import Path
import inspect
import json
import shutil
import subprocess
from PIL import Image

from .triposr_backend import TripoSRBackend
from .character_hd_backend import CharacterHDBackend
from .character_visual_qa import CharacterVisualQA
from .image_preprocess import prepare_character_hd_reference
from app.modules.nhan_vat_2d.visual_intent import VisualIntentInterpreter, apply_beauty_preset
from app.modules.nhan_vat_2d.spec_parser import parse_character_spec
from app.core.prompt_contract import build_priority_prompt


def _enrich_concept_prompt(interpreter: VisualIntentInterpreter, prompt: str) -> str:
    """Same vague-beauty-language translation as nhan_vat_2d (visual_intent.py),
    reused here so text-to-3D's concept-image step isn't limited to the raw
    prompt tail either - the concept image quality directly determines the
    3D mesh quality downstream, so this is not cosmetic."""
    spec = parse_character_spec(prompt)
    intent = interpreter.interpret(prompt)
    intent = apply_beauty_preset(intent, spec.gender, prompt)
    extra = []
    for key in ("face_beauty", "body_style", "hair_style", "costume_style",
                "pose_style", "camera_style", "lighting_style", "render_style"):
        extra.extend(intent.get(key) or [])
    return build_priority_prompt(
        prompt,
        mandatory=[
            "single full-body character or isolated object exactly as requested",
            "entire silhouette visible; required weapon or equipment fully readable",
        ],
        composition=["centered neutral standing pose if character; front or slight three-quarter view; plain background"],
        quality=extra + ["clean concept image for 3D reconstruction; no text"],
        max_words=62,
        core_max_words=32,
        core_label="3D SUBJECT AND REQUIRED DESIGN",
    )


class Local3DService:
    def __init__(self, triposr_dir: str | Path, model_cache: str | Path, image_service=None,
                 root: str | Path | None = None):
        self.triposr = TripoSRBackend(triposr_dir, model_cache)
        self.root = Path(root).resolve() if root else self.triposr.root
        self.character_hd = CharacterHDBackend(self.root, Path(model_cache).resolve() / "character_hd")
        self.image_service = image_service
        self.visual_intent = VisualIntentInterpreter()
        self.character_visual_qa = CharacterVisualQA()

    def _normalize_generated_character(self, result: dict, backend: str, progress=None) -> dict:
        model_path = Path(result["model_path"]).resolve()
        script = self.root / "app" / "modules" / "nhan_vat_3d" / "character_normalize.py"
        python = self.character_hd.python if backend == "character_hd" else self.triposr.runtime_python
        normalized = model_path.with_name(model_path.stem + "_normalized.glb")
        if progress:
            progress(99, "Chuẩn hóa nhân vật 3D", "Y-up · 1.8m · center · ground · kiểm tra GLB")
        proc = subprocess.run(
            [str(python), str(script), str(model_path), str(normalized)],
            cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        marker = "AIVF_CHARACTER_NORMALIZED|"
        line = next((item for item in reversed(proc.stdout.splitlines()) if item.startswith(marker)), None)
        if proc.returncode or not line or not normalized.is_file():
            detail = (proc.stderr or proc.stdout or "character normalization failed")[-4000:]
            raise RuntimeError("Chuẩn hóa nhân vật 3D thất bại:\n" + detail)
        report = json.loads(line[len(marker):])
        if not report.get("geometry_pass") or not report.get("ground_pass") or not report.get("export_roundtrip_pass"):
            raise RuntimeError("GLB không qua geometry/ground/export validation: " + json.dumps(report, ensure_ascii=False))
        result = dict(result)
        result["model_path"] = normalized
        result["normalization"] = report
        return result

    def _visual_qa_generated_character(self, result: dict, backend: str, source_image: str | Path,
                                       attempt: int, progress=None) -> dict:
        model_path = Path(result["model_path"]).resolve()
        render_script = self.root / "app" / "modules" / "nhan_vat_3d" / "character_qa_render.py"
        qa_dir = model_path.parent / "visual_qa"
        if progress:
            progress(99, "Render Visual QA", f"{backend} · candidate {attempt} · 5 camera views")
        proc = subprocess.run(
            [str(self.triposr.runtime_python), str(render_script), str(model_path), str(qa_dir)],
            cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        marker = "AIVF_QA_RENDERS|"
        line = next((item for item in reversed(proc.stdout.splitlines()) if item.startswith(marker)), None)
        if proc.returncode or not line:
            detail = (proc.stderr or proc.stdout or "QA rendering failed")[-4000:]
            raise RuntimeError("Render Character Visual QA thất bại:\n" + detail)
        render_info = json.loads(line[len(marker):])
        evaluation = self.character_visual_qa.evaluate(render_info["views"], qa_dir)
        normalization = result.get("normalization") or {}
        geometry_ready = bool(
            normalization.get("geometry_pass") and normalization.get("ground_pass")
            and normalization.get("pivot_center_pass") and normalization.get("export_roundtrip_pass")
        )
        ready = bool(backend == "character_hd" and geometry_ready and evaluation.get("status") == "PASS")
        source = Path(source_image).resolve()
        source_copy = qa_dir / ("source_reference" + (source.suffix.lower() or ".png"))
        shutil.copy2(source, source_copy)
        result = dict(result)
        result["visual_qa"] = {
            **evaluation, **render_info, "attempt": attempt, "backend": backend,
            "geometry_ready": geometry_ready, "ready_for_rig": ready,
        }
        result["source_image"] = str(source_copy)
        result["ready_for_rig"] = ready
        result["quality_stage"] = "FINAL" if ready else "DRAFT"
        return result

    @staticmethod
    def _candidate_score(result: dict) -> float:
        value = (result.get("visual_qa") or {}).get("score")
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1.0

    @classmethod
    def _candidate_rank(cls, result: dict) -> tuple[int, float]:
        return (1 if (result.get("visual_qa") or {}).get("status") == "PASS" else 0, cls._candidate_score(result))

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
            candidates = []
            prepared_image = prepare_character_hd_reference(
                image_path, Path(work_dir).resolve() / "character_hd_reference.png"
            )
            for attempt in range(1, 4):
                attempt_dir = Path(work_dir).resolve() / f"candidate_{attempt}"
                result = self.character_hd.generate(
                    prepared_image, attempt_dir, texture=texture, optimize_mesh=optimize_mesh,
                    mesh_profile=mesh_profile, progress=progress, cancel_event=cancel_event,
                )
                result = self._normalize_generated_character(result, "character_hd", progress)
                result = self._visual_qa_generated_character(result, "character_hd", image_path, attempt, progress)
                candidates.append(result)
                status = (result.get("visual_qa") or {}).get("status")
                if status in {"PASS", "UNSUPPORTED"}:
                    break
            selected = max(candidates, key=self._candidate_rank)
            selected_index = candidates.index(selected) + 1
            selected = dict(selected)
            selected["attempt_count"] = len(candidates)
            selected["retry_count"] = max(0, len(candidates) - 1)
            selected["selected_candidate"] = selected_index
            selected["candidates"] = [
                {"attempt": index + 1, "score": self._candidate_score(item),
                 "status": (item.get("visual_qa") or {}).get("status"),
                 "model_path": str(item.get("model_path"))}
                for index, item in enumerate(candidates)
            ]
            return selected
        result = self.triposr.generate(
            image_path, work_dir, resolution=resolution,
            texture=texture, render_preview=render_preview, progress=progress, cancel_event=cancel_event,
        )
        # The HD mesh profiles apply only to Character HD; avoid displaying an
        # HD/Medium/Light badge on TripoSR results.
        result["mesh_profile"] = "original"
        result = self._normalize_generated_character(result, "quick", progress)
        result = self._visual_qa_generated_character(result, "quick", image_path, 1, progress)
        result["attempt_count"] = 1
        result["retry_count"] = 0
        result["selected_candidate"] = 1
        result["ready_for_rig"] = False
        result["quality_stage"] = "DRAFT"
        return result

    def colorize_existing(self, mesh_path: str | Path, image_path: str | Path, work_dir: str | Path, *, progress=None,
                          cancel_event=None, timeout_seconds: int | None = None, idle_timeout_seconds: int | None = None) -> dict:
        self._validate_image(image_path)
        mesh_path = Path(mesh_path)
        if not mesh_path.exists() or mesh_path.suffix.lower() != ".glb":
            raise ValueError("Model để tô màu phải là file GLB hợp lệ")
        kwargs = {}
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        if idle_timeout_seconds is not None:
            kwargs["idle_timeout_seconds"] = idle_timeout_seconds
        return self.character_hd.paint_existing(mesh_path, image_path, work_dir, progress=progress, cancel_event=cancel_event, **kwargs)

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
        enriched_prompt = _enrich_concept_prompt(self.visual_intent, prompt)
        concept = self.image_service.generate(enriched_prompt, **image_kwargs)
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
