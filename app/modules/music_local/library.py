"""Free local music library indexing and keyword recommendation."""
from __future__ import annotations

import re
from pathlib import Path

_ALLOWED = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
_TAGS = {
    "vui": ["happy", "upbeat", "pop", "fun"], "nhanh": ["fast", "energetic", "dance", "edm"],
    "gaming": ["game", "gaming", "electronic", "edm"], "game": ["game", "gaming", "electronic"],
    "chill": ["chill", "lofi", "relax", "ambient"], "buồn": ["sad", "emotional", "piano"],
    "cinematic": ["cinematic", "epic", "trailer", "orchestra"], "điện ảnh": ["cinematic", "epic", "trailer"],
    "cute": ["cute", "happy", "playful"], "hài": ["funny", "comedy", "playful"],
}


class LocalMusicLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict]:
        items = []
        for path in sorted(self.root.iterdir()):
            if path.is_file() and path.suffix.lower() in _ALLOWED:
                items.append({"id": path.name, "name": path.stem, "path": str(path), "tags": self._tokens(path.stem)})
        return items

    def search(self, wish: str, limit: int = 18) -> dict:
        wish_clean = re.sub(r"\s+", " ", (wish or "").lower()).strip()
        wanted = set(self._tokens(wish_clean))
        for key, tags in _TAGS.items():
            if key in wish_clean:
                wanted.update(tags)
        ranked = []
        for item in self.list():
            tags = set(item["tags"])
            score = len(tags & wanted)
            if not wanted:
                score = 1
            ranked.append((score, item))
        ranked.sort(key=lambda row: (row[0], row[1]["name"]), reverse=True)
        return {"query": " ".join(sorted(wanted)) or wish_clean, "items": [item for score, item in ranked if score > 0][:limit]}

    def path(self, track_id: str) -> Path:
        safe = Path(track_id).name
        path = (self.root / safe).resolve()
        if path.parent != self.root or not path.is_file() or path.suffix.lower() not in _ALLOWED:
            raise ValueError("Không tìm thấy nhạc local")
        return path

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [x for x in re.findall(r"[a-zA-Z0-9À-ỹ]+", text.lower()) if len(x) > 1]
