from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import Any


DEFAULT_VIDEO_PLAYBOOK: dict[str, Any] = {
    "version": 1,
    "name": "YouTube Production Playbook V1",
    "rules": {
        "content": [
            "Hook appears in first 3-5 seconds and states why the viewer should continue.",
            "First 10-15 seconds clarify topic, reason to watch, and payoff.",
            "Do not open with a long greeting; go directly into the content.",
            "Use truthful curiosity loops; no fake clickbait.",
            "Each scene must serve information, emotion, or story continuity; remove scenes that serve none.",
            "CTA must be natural, relevant, and not too early.",
            "Ending should reconnect to the opening hook when appropriate.",
        ],
        "pacing": [
            "Create a visual or informational change when content rhythm needs it; typical range 5-15 seconds, not as a rigid rule.",
            "Opening is direct and relatively fast; middle allows explanation; climax may increase rhythm; ending slows enough for comprehension.",
            "Do not use fast editing without narrative purpose.",
        ],
        "scene_contract": [
            "Each scene has purpose, exact voice-over, visuals, subject/character, environment, camera, motion, lighting, on-screen text, SFX, music, and transition where relevant.",
            "Video prompt order: SUBJECT -> ACTION -> ENVIRONMENT -> CAMERA -> LIGHTING -> STYLE -> MOTION -> SOUND -> QUALITY -> NEGATIVE.",
            "If image-to-video is appropriate, provide IMAGE PROMPT and MOTION PROMPT separately.",
        ],
        "consistency": [
            "Script is source of truth for content.",
            "Reference image is source of truth for appearance when provided.",
            "Preserve face, age, hair, costume, colors, body proportions, and visual style across scenes.",
            "Preserve architecture and basic layout when returning to the same location.",
        ],
        "quality": [
            "Images must be clean, subject-readable, coherent, and free from obvious anatomy/object deformation.",
            "Avoid AI text artifacts inside generated imagery unless text is explicitly rendered by a dedicated text layer.",
            "Voice-over should sound natural, use short clear sentences, avoid repetition and unnecessary jargon, and fit scene timing.",
            "Before final output, run QA for hook, retention, repetition, scene length, visual relevance, transitions, voice timing, value, CTA, and ending connection.",
        ],
    },
}


class DirectorMemoryStore:
    """Small persistent JSON memory for AI Video Director.

    It does NOT fine-tune or mutate model weights. Memory is explicit, scoped and auditable.
    Priority when resolving memory:
      user command > project memory > playbook > feedback memory > model defaults
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.playbook_path = self.root / "video_playbook.json"
        self.projects_path = self.root / "project_memory.json"
        self.feedback_path = self.root / "feedback_memory.json"
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        with self._lock:
            if not self.playbook_path.exists():
                self._write(self.playbook_path, DEFAULT_VIDEO_PLAYBOOK)
            if not self.projects_path.exists():
                self._write(self.projects_path, {"projects": {}})
            if not self.feedback_path.exists():
                self._write(self.feedback_path, {"feedback": []})

    @staticmethod
    def _read(path: Path, fallback: Any) -> Any:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
        except Exception:
            return fallback

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_playbook(self) -> dict[str, Any]:
        with self._lock:
            return self._read(self.playbook_path, DEFAULT_VIDEO_PLAYBOOK)

    def set_playbook(self, playbook: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(playbook, dict) or not playbook:
            raise ValueError("Playbook phải là object JSON không rỗng")
        with self._lock:
            payload = dict(playbook)
            payload["updated_at"] = time.time()
            self._write(self.playbook_path, payload)
            return payload

    def get_project(self, project_id: str | None) -> dict[str, Any]:
        if not project_id:
            return {}
        pid = str(project_id).strip()
        if not pid:
            return {}
        with self._lock:
            data = self._read(self.projects_path, {"projects": {}})
            return dict((data.get("projects") or {}).get(pid) or {})

    def upsert_project(self, project_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        pid = str(project_id or "").strip()
        if not pid:
            raise ValueError("Thiếu project_id")
        if not isinstance(memory, dict):
            raise ValueError("project memory phải là object")
        with self._lock:
            data = self._read(self.projects_path, {"projects": {}})
            projects = data.setdefault("projects", {})
            current = dict(projects.get(pid) or {})
            current.update(memory)
            current["updated_at"] = time.time()
            projects[pid] = current
            self._write(self.projects_path, data)
            return current

    def add_feedback(self, *, text: str, project_id: str | None = None, scope: str = "video", kind: str = "preference") -> dict[str, Any]:
        clean = str(text or "").strip()
        if len(clean) < 3:
            raise ValueError("Feedback quá ngắn")
        if kind not in {"preference", "avoid", "approved", "correction"}:
            raise ValueError("kind không hợp lệ")
        entry = {
            "id": f"fb_{int(time.time()*1000)}",
            "text": clean,
            "project_id": str(project_id).strip() if project_id else None,
            "scope": str(scope or "video").strip() or "video",
            "kind": kind,
            "created_at": time.time(),
            "active": True,
        }
        with self._lock:
            data = self._read(self.feedback_path, {"feedback": []})
            items = data.setdefault("feedback", [])
            items.append(entry)
            data["feedback"] = items[-500:]
            self._write(self.feedback_path, data)
        return entry

    def list_feedback(self, project_id: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read(self.feedback_path, {"feedback": []})
            items = [x for x in data.get("feedback", []) if isinstance(x, dict) and x.get("active", True)]
        if project_id:
            pid = str(project_id).strip()
            items = [x for x in items if x.get("project_id") in {None, pid}]
        return items[-max(1, min(int(limit), 200)):]

    def resolve(self, *, project_id: str | None = None, user_command: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return memory context with explicit priority, without mutating source memories."""
        return {
            "priority": ["user_command", "project_memory", "video_playbook", "feedback_memory", "model_defaults"],
            "user_command": dict(user_command or {}),
            "project_memory": self.get_project(project_id),
            "video_playbook": self.get_playbook(),
            "feedback_memory": self.list_feedback(project_id, limit=40),
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            projects = self._read(self.projects_path, {"projects": {}}).get("projects", {})
            feedback = self._read(self.feedback_path, {"feedback": []}).get("feedback", [])
        return {
            "ready": True,
            "playbook": self.get_playbook().get("name", "Video Playbook"),
            "project_count": len(projects or {}),
            "feedback_count": len(feedback or []),
            "storage": str(self.root),
            "model_weights_modified": False,
        }
