from __future__ import annotations

import json
import os
import re
import shutil
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[a-f0-9]{32}$")


class Model3DLibrary:
    """Persistent local GLB library.

    Saving a model never runs AI, Blender, rigging, or animation. On NTFS/same
    volume it prefers a hard-link, which is nearly instant and avoids duplicating
    the GLB bytes. It falls back to a normal copy when hard-linking is unavailable.
    """

    def __init__(self, root: str | Path, workspace):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace

    def _item_dir(self, item_id: str) -> Path:
        item_id = str(item_id or "").strip().lower()
        if not _SAFE_ID.fullmatch(item_id):
            raise ValueError("ID thư viện 3D không hợp lệ")
        path = (self.root / item_id).resolve()
        if self.root not in path.parents:
            raise ValueError("Đường dẫn thư viện 3D không hợp lệ")
        return path

    @staticmethod
    def _clean_name(name: str | None) -> str:
        value = " ".join(str(name or "").strip().split()) or "Model 3D"
        return value[:80]

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _inspect_glb(path: Path) -> dict[str, Any]:
        """Read only the tiny JSON chunk; no mesh decoding and no extra dependency."""
        result: dict[str, Any] = {"parts": 0, "triangles": 0, "animations": [], "skinned": False}
        try:
            with path.open("rb") as f:
                header = f.read(12)
                if len(header) != 12 or header[:4] != b"glTF":
                    return result
                while True:
                    chunk_header = f.read(8)
                    if len(chunk_header) != 8:
                        break
                    length, chunk_type = struct.unpack("<II", chunk_header)
                    data = f.read(length)
                    if chunk_type == 0x4E4F534A:
                        doc = json.loads(data.decode("utf-8").rstrip("\x00 \t\r\n"))
                        accessors = doc.get("accessors") or []
                        parts = 0
                        triangles = 0
                        for mesh in doc.get("meshes") or []:
                            for prim in mesh.get("primitives") or []:
                                parts += 1
                                if int(prim.get("mode", 4)) != 4:
                                    continue
                                idx = prim.get("indices")
                                if isinstance(idx, int) and 0 <= idx < len(accessors):
                                    triangles += int(accessors[idx].get("count") or 0) // 3
                                else:
                                    pos = (prim.get("attributes") or {}).get("POSITION")
                                    if isinstance(pos, int) and 0 <= pos < len(accessors):
                                        triangles += int(accessors[pos].get("count") or 0) // 3
                        result.update({
                            "parts": parts,
                            "triangles": triangles,
                            "animations": [str(a.get("name") or f"clip_{i+1}") for i, a in enumerate(doc.get("animations") or [])],
                            "skinned": bool(doc.get("skins")),
                        })
                        break
        except Exception:
            pass
        return result

    def _write_meta(self, item_dir: Path, meta: dict[str, Any]) -> None:
        (item_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_source_item(self, source_asset_id: str) -> tuple[str, Path, dict[str, Any]] | None:
        for d in self.root.iterdir():
            if not d.is_dir() or not _SAFE_ID.fullmatch(d.name):
                continue
            meta = self._read_json(d / "meta.json")
            if meta.get("source_asset_id") == source_asset_id and (d / "model.glb").exists():
                return d.name, d, meta
        return None

    @staticmethod
    def _link_or_copy(source: Path, target: Path) -> str:
        if target.exists():
            target.unlink()
        try:
            os.link(source, target)
            return "hardlink"
        except Exception:
            shutil.copy2(source, target)
            return "copy"

    def save(self, asset_id: str, *, name: str | None = None) -> dict[str, Any]:
        asset_id = str(asset_id or "").strip()
        if not asset_id:
            raise ValueError("Thiếu asset_id của model đang xem")
        source = Path(self.workspace.model_path(asset_id)).resolve()
        if not source.exists() or source.suffix.lower() != ".glb":
            raise ValueError("Không tìm thấy GLB nguồn để lưu vào thư viện")

        existing = self._find_source_item(asset_id)
        if existing:
            item_id, item_dir, old_meta = existing
        else:
            item_id = uuid.uuid4().hex
            item_dir = self.root / item_id
            item_dir.mkdir(parents=True, exist_ok=True)
            old_meta = {}

        storage_method = self._link_or_copy(source, item_dir / "model.glb")
        now = datetime.now(timezone.utc).isoformat()
        inspect = self._inspect_glb(item_dir / "model.glb")
        meta: dict[str, Any] = {
            **old_meta,
            **inspect,
            "id": item_id,
            "name": self._clean_name(name or old_meta.get("name")),
            "source_asset_id": asset_id,
            "saved_at": old_meta.get("saved_at") or now,
            "updated_at": now,
            "size_bytes": (item_dir / "model.glb").stat().st_size,
            "storage_method": storage_method,
            "game_ready": bool(inspect.get("skinned") and inspect.get("animations")),
        }
        self._write_meta(item_dir, meta)
        return self.public_item(meta)

    def public_item(self, meta: dict[str, Any]) -> dict[str, Any]:
        item_id = str(meta.get("id") or "")
        out = dict(meta)
        out["model_url"] = f"/api/3d/library/{item_id}/model"
        return out

    def list_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for d in self.root.iterdir():
            if not d.is_dir() or not _SAFE_ID.fullmatch(d.name) or not (d / "model.glb").exists():
                continue
            meta = self._read_json(d / "meta.json")
            if not meta:
                meta = {
                    "id": d.name,
                    "name": "Model 3D",
                    "saved_at": datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc).isoformat(),
                    **self._inspect_glb(d / "model.glb"),
                }
            meta["id"] = d.name
            meta["size_bytes"] = (d / "model.glb").stat().st_size
            items.append(self.public_item(meta))
        items.sort(key=lambda x: str(x.get("updated_at") or x.get("saved_at") or ""), reverse=True)
        return items

    def model_path(self, item_id: str) -> Path:
        path = self._item_dir(item_id) / "model.glb"
        if not path.exists():
            raise ValueError("Model không còn trong thư viện 3D")
        return path

    def restore(self, item_id: str) -> dict[str, Any]:
        item_dir = self._item_dir(item_id)
        meta = self._read_json(item_dir / "meta.json")
        source_asset_id = str(meta.get("source_asset_id") or "")
        if source_asset_id:
            try:
                source = Path(self.workspace.model_path(source_asset_id))
                if source.exists():
                    return {"asset_id": source_asset_id, "restored": False}
            except Exception:
                pass
        payload = self.workspace.create_asset(
            self.model_path(item_id), None,
            {"source": "3d_library", "library_id": item_id, "game_ready": bool(meta.get("game_ready")), "animations": meta.get("animations") or []},
        )
        return {"asset_id": payload["asset_id"], "restored": True}

    def delete(self, item_id: str) -> dict[str, Any]:
        item_dir = self._item_dir(item_id)
        if not item_dir.exists():
            raise ValueError("Model không còn trong thư viện 3D")
        meta = self._read_json(item_dir / "meta.json")
        name = meta.get("name") or "Model 3D"
        shutil.rmtree(item_dir)
        return {"ok": True, "id": item_id, "name": name}
