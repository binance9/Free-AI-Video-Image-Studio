"""File-backed editing sessions for the browser video studio."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from .errors import InvalidVideoRequest
from .probe import probe_video

_SESSION_RE = re.compile(r"^[a-f0-9]{32}$")
_ASSET_RE = re.compile(r"^[a-f0-9]{32}\.(png|jpg|jpeg|webp|gif)$")
_AUDIO_RE = re.compile(r"^[a-f0-9]{32}\.(mp3|wav|m4a|aac|ogg|flac)$")
_ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
_ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_ALLOWED_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


class VideoWorkspace:
    """Keep non-destructive editor versions and overlay assets per upload."""

    def __init__(self, root: str | Path, builtin_sticker_dir: str | Path | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.builtin_sticker_dir = Path(builtin_sticker_dir).resolve() if builtin_sticker_dir else None

    def create(self, source: str | Path, original_name: str) -> dict:
        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise InvalidVideoRequest("Video upload does not exist")
        suffix = source_path.suffix.lower() or ".mp4"
        if suffix not in _ALLOWED_VIDEO_SUFFIXES:
            raise InvalidVideoRequest("Unsupported video format")
        session_id = uuid4().hex
        folder = self.root / session_id
        (folder / "assets").mkdir(parents=True, exist_ok=False)
        (folder / "audio").mkdir(parents=True, exist_ok=False)
        current = folder / f"version_000{suffix}"
        shutil.move(str(source_path), current)
        manifest = {
            "session_id": session_id,
            "original_name": self._safe_name(original_name, suffix),
            "versions": [current.name],
            "current_index": 0,
            "history": ["Đã tải video gốc"],
        }
        self._write(folder, manifest)
        return self.describe(session_id)

    def current_path(self, session_id: str) -> Path:
        folder, manifest = self._load(session_id)
        path = folder / manifest["versions"][int(manifest["current_index"])]
        if not path.is_file():
            raise InvalidVideoRequest("Current edited video is missing")
        return path

    def add_version(self, session_id: str, generated: str | Path, label: str) -> dict:
        folder, manifest = self._load(session_id)
        generated_path = Path(generated).resolve()
        if not generated_path.is_file():
            raise InvalidVideoRequest("Edited video was not created")
        current_index = int(manifest["current_index"])
        versions = list(manifest["versions"][: current_index + 1])
        history = list(manifest["history"][: current_index + 1])
        suffix = generated_path.suffix.lower() or ".mp4"
        if suffix not in _ALLOWED_VIDEO_SUFFIXES:
            suffix = ".mp4"
        target = folder / f"version_{len(versions):03d}{suffix}"
        if generated_path != target:
            target.unlink(missing_ok=True)
            shutil.move(str(generated_path), target)
        versions.append(target.name)
        history.append(label)
        manifest["versions"], manifest["history"] = versions, history
        manifest["current_index"] = len(versions) - 1
        self._write(folder, manifest)
        return self.describe(session_id)

    def next_output(self, session_id: str) -> Path:
        return self.folder(session_id) / f"render_{uuid4().hex}.mp4"

    def save_asset(self, session_id: str, uploaded_path: str | Path, original_name: str) -> dict:
        folder, _ = self._load(session_id)
        source = Path(uploaded_path).resolve()
        suffix = Path(original_name or source.name).suffix.lower() or source.suffix.lower()
        if suffix not in _ALLOWED_IMAGE_SUFFIXES:
            source.unlink(missing_ok=True)
            raise InvalidVideoRequest("Chỉ hỗ trợ PNG, JPG, WebP hoặc GIF")
        target = folder / "assets" / f"{uuid4().hex}{suffix}"
        shutil.move(str(source), target)
        return {"asset_id": target.name, "url": f"/api/editor/{session_id}/asset/{target.name}", "name": Path(original_name).name}


    def save_audio(self, session_id: str, uploaded_path: str | Path, original_name: str) -> dict:
        folder, _ = self._load(session_id)
        source = Path(uploaded_path).resolve()
        suffix = Path(original_name or source.name).suffix.lower() or source.suffix.lower()
        if suffix not in _ALLOWED_AUDIO_SUFFIXES:
            source.unlink(missing_ok=True)
            raise InvalidVideoRequest("Chỉ hỗ trợ MP3, WAV, M4A, AAC, OGG hoặc FLAC")
        target = folder / "audio" / f"{uuid4().hex}{suffix}"
        shutil.move(str(source), target)
        return {"audio_id": target.name, "name": Path(original_name).name}

    def audio_path(self, session_id: str, audio_id: str) -> Path:
        folder, _ = self._load(session_id)
        if not _AUDIO_RE.fullmatch(audio_id or ""):
            raise InvalidVideoRequest("Invalid audio id")
        path = (folder / "audio" / audio_id).resolve()
        if path.parent != (folder / "audio").resolve() or not path.is_file():
            raise InvalidVideoRequest("Audio not found")
        return path

    def import_ai_image(self, session_id: str, image_path: str | Path) -> dict:
        folder, _ = self._load(session_id)
        source = Path(image_path).resolve()
        if not source.is_file():
            raise InvalidVideoRequest("AI image not found")
        target = folder / "assets" / f"{uuid4().hex}.png"
        shutil.copy2(source, target)
        return {"asset_id": target.name, "url": f"/api/editor/{session_id}/asset/{target.name}", "name": "AI image.png"}

    def asset_path(self, session_id: str, asset_id: str) -> Path:
        folder, _ = self._load(session_id)
        if not _ASSET_RE.fullmatch(asset_id or ""):
            raise InvalidVideoRequest("Invalid asset id")
        path = (folder / "assets" / asset_id).resolve()
        if path.parent != (folder / "assets").resolve() or not path.is_file():
            raise InvalidVideoRequest("Asset not found")
        return path

    def builtin_sticker_path(self, name: str) -> Path:
        if not self.builtin_sticker_dir:
            raise InvalidVideoRequest("Sticker library is unavailable")
        raw = Path(name or "").name
        if raw != name:
            raise InvalidVideoRequest("Invalid sticker name")
        safe = raw if raw.lower().endswith(".png") else f"{raw}.png"
        path = (self.builtin_sticker_dir / safe).resolve()
        if path.parent != self.builtin_sticker_dir or not path.is_file():
            raise InvalidVideoRequest("Sticker not found")
        return path

    def undo(self, session_id: str) -> dict:
        folder, manifest = self._load(session_id)
        index = int(manifest["current_index"])
        if index <= 0:
            raise InvalidVideoRequest("Đang ở video gốc, không còn bước để hoàn tác")
        manifest["current_index"] = index - 1
        self._write(folder, manifest)
        return self.describe(session_id)

    def describe(self, session_id: str) -> dict:
        folder, manifest = self._load(session_id)
        info = probe_video(self.current_path(session_id))
        index = int(manifest["current_index"])
        return {
            "session_id": session_id,
            "original_name": manifest["original_name"],
            "version": index,
            "duration": round(info.duration, 3),
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "has_audio": info.has_audio,
            "can_undo": index > 0,
            "history": manifest["history"][: index + 1],
        }

    def folder(self, session_id: str) -> Path:
        folder, _ = self._load(session_id)
        return folder

    def _load(self, session_id: str) -> tuple[Path, dict]:
        if not _SESSION_RE.fullmatch(session_id or ""):
            raise InvalidVideoRequest("Invalid editor session")
        folder = (self.root / session_id).resolve()
        if folder.parent != self.root or not folder.is_dir():
            raise InvalidVideoRequest("Editor session not found")
        try:
            manifest = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidVideoRequest("Editor session is damaged") from exc
        return folder, manifest

    @staticmethod
    def _write(folder: Path, manifest: dict) -> None:
        (folder / "session.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _safe_name(name: str, suffix: str) -> str:
        cleaned = Path(name or f"video{suffix}").name.strip()
        return cleaned or f"video{suffix}"
