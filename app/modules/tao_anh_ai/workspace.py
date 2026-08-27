"""Persistent local workspace for AI-generated and AI-edited images."""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

_ID_RE = re.compile(r"^[a-f0-9]{32}\.png$")


class AiImageWorkspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, image_bytes: bytes) -> dict:
        image_id = f"{uuid4().hex}.png"
        path = self.root / image_id
        path.write_bytes(image_bytes)
        return {"image_id": image_id, "url": f"/api/ai-image/{image_id}"}

    def path(self, image_id: str) -> Path:
        if not _ID_RE.fullmatch(image_id or ""):
            raise ValueError("Invalid AI image id")
        path = (self.root / image_id).resolve()
        if path.parent != self.root or not path.is_file():
            raise ValueError("AI image not found")
        return path
