"""Ollama local client cho Gà Inspector.

Giao tiếp với Ollama REST API (mặc định http://localhost:11434).
Hỗ trợ:
  - analyze_error(code, error, context) → nguyên nhân + đề xuất sửa
  - suggest_fix(code, error, file_path) → diff tối thiểu
  - summarize_report(items) → tóm tắt tình trạng module
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    timeout: int = 120


class InspectorOllama:
    """Wrapper tối giản cho Ollama REST API."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.cfg = config or OllamaConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Kiểm tra Ollama có chạy không."""
        try:
            resp = self._post("/api/tags", {})
            models = [m.get("name", "") for m in resp.get("models", [])]
            return {"ok": True, "models": models, "model": self.cfg.model}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "model": self.cfg.model}

    def analyze_error(
        self,
        code: str,
        error: str,
        file_path: str = "",
        context: str = "",
    ) -> dict[str, Any]:
        """Phân tích lỗi và đề xuất nguyên nhân."""
        prompt = self._build_analysis_prompt(code, error, file_path, context)
        raw = self._chat(prompt)
        return self._parse_analysis(raw)

    def suggest_fix(
        self,
        code: str,
        error: str,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Đề xuất sửa code tối thiểu."""
        prompt = self._build_fix_prompt(code, error, file_path)
        raw = self._chat(prompt)
        return self._parse_fix(raw)

    def summarize(self, items: list[dict]) -> str:
        """Tóm tắt danh sách lỗi."""
        lines = []
        for i, it in enumerate(items, 1):
            lines.append(f"{i}. [{it.get('severity','?')}] {it.get('file','?')}:{it.get('line','?')} — {it.get('message','?')}")
        prompt = (
            "Tóm tắt tình trạng code sau thành 2-3 câu. "
            "Nêu điểm mạnh, điểm yếu, và ưu tiên sửa. Viết tiếng Việt:\n\n"
            + "\n".join(lines)
        )
        return self._chat(prompt).strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_analysis_prompt(self, code: str, error: str, file_path: str, context: str) -> str:
        parts = [
            "Bạn là chuyên gia kiểm tra code Python. Phân tích lỗi sau và tìm nguyên nhân gốc rễ.",
            f"File: {file_path}" if file_path else "File: (không rõ)",
            f"Context: {context}" if context else "",
            f"Lỗi:\n{error}",
            f"Code:\n{code[:4000]}",
            "",
            "Trả lời theo format JSON:",
            '{"cause": "nguyên nhân gốc rễ", "severity": "critical|high|medium|low", "suggestion": "đề xuất sửa tối thiểu", "affected_files": ["file1.py"]}',
        ]
        return "\n".join(p for p in parts if p)

    def _build_fix_prompt(self, code: str, error: str, file_path: str) -> str:
        return (
            "Bạn là chuyên gia sửa code Python. Sửa lỗi sau với thay đổi TỐI THIỂU.\n"
            "KHÔNG refactor, KHÔNG đổi tên biến, KHÔNG xóa code không liên quan.\n"
            f"File: {file_path}\n"
            f"Lỗi:\n{error}\n"
            f"Code hiện tại:\n{code[:6000]}\n\n"
            "Trả lời theo format JSON:\n"
            '{"fixed_code": "toàn bộ code đã sửa", "changes": ["mô tả từng thay đổi"], "rationale": "lý do"}'
        )

    def _parse_analysis(self, raw: str) -> dict[str, Any]:
        """Trích JSON từ response text."""
        text = raw.strip()
        # Thử tìm JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "cause": text[:500],
            "severity": "unknown",
            "suggestion": "",
            "affected_files": [],
            "raw": raw,
        }

    def _parse_fix(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"fixed_code": "", "changes": [], "rationale": raw[:500], "raw": raw}

    def _chat(self, prompt: str) -> str:
        """Gọi Ollama /api/chat."""
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 8192},
        }
        resp = self._post("/api/chat", body)
        # chat response: {"message": {"content": "..."}}
        msg = resp.get("message", {})
        return msg.get("content", "")

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.cfg.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
