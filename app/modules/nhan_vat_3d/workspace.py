"""Persistent workspace for generated 3D models and turntable previews."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path


class Model3DWorkspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_asset(self, model_path: str | Path, preview_path: str | Path | None, metadata: dict) -> dict:
        asset_id = uuid.uuid4().hex
        folder = self.root / asset_id
        folder.mkdir(parents=True, exist_ok=False)
        source = Path(model_path)
        model_name = "model" + source.suffix.lower()
        shutil.copy2(source, folder / model_name)
        preview_name = None
        if preview_path and Path(preview_path).exists():
            p = Path(preview_path)
            preview_name = "preview" + p.suffix.lower()
            shutil.copy2(p, folder / preview_name)
        metadata = dict(metadata)
        source_image = metadata.get("source_image")
        if source_image and Path(source_image).is_file():
            source = Path(source_image)
            source_name = "source_reference" + (source.suffix.lower() or ".png")
            shutil.copy2(source, folder / source_name)
            metadata["source_image"] = source_name
        visual_qa = metadata.get("visual_qa")
        if isinstance(visual_qa, dict):
            visual_qa = dict(visual_qa)
            qa_folder = folder / "visual_qa"
            qa_folder.mkdir(exist_ok=True)
            copied_views = {}
            for view, value in (visual_qa.get("views") or {}).items():
                source = Path(value)
                if source.is_file():
                    name = f"{view}.png"
                    shutil.copy2(source, qa_folder / name)
                    copied_views[view] = f"visual_qa/{name}"
            visual_qa["views"] = copied_views
            montage = Path(str(visual_qa.get("montage") or ""))
            if montage.is_file():
                shutil.copy2(montage, qa_folder / "qa_montage.jpg")
                visual_qa["montage"] = "visual_qa/qa_montage.jpg"
            metadata["visual_qa"] = visual_qa
        payload = {"asset_id": asset_id, "model": model_name, "preview": preview_name, **metadata}
        (folder / "meta.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def metadata(self, asset_id: str) -> dict:
        folder = self._folder(asset_id)
        path = folder / "meta.json"
        if not path.exists():
            raise ValueError("Không tìm thấy model 3D")
        return json.loads(path.read_text(encoding="utf-8"))

    def model_path(self, asset_id: str) -> Path:
        meta = self.metadata(asset_id)
        path = self._folder(asset_id) / meta["model"]
        if not path.exists():
            raise ValueError("File model 3D không còn tồn tại")
        return path

    def preview_path(self, asset_id: str) -> Path:
        meta = self.metadata(asset_id)
        if not meta.get("preview"):
            raise ValueError("Model này chưa có preview")
        path = self._folder(asset_id) / meta["preview"]
        if not path.exists():
            raise ValueError("Preview không còn tồn tại")
        return path

    def _folder(self, asset_id: str) -> Path:
        clean = "".join(c for c in str(asset_id) if c.isalnum())
        if clean != asset_id or len(clean) < 8:
            raise ValueError("Mã model 3D không hợp lệ")
        return self.root / clean
