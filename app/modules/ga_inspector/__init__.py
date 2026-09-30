"""Gà Inspector — Module kiểm tra code tự động.

Workflow:
  1. Chọn scope: 1 file, 1 module/folder, hoặc toàn project
  2. Quét AST + phân tích import/lint
  3. Dùng Ollama local để phân tích lỗi và đề xuất sửa
  4. Tạo report markdown (PASS/FAIL, file, dòng, nguyên nhân, đề xuất)
  5. Backup/checkpoint trước khi sửa code tối thiểu
  6. Tự test lại sau khi sửa

KHÔNG sửa AI core (ga_brain, ga_owner, ga_maintenance).
"""
from __future__ import annotations

from .service import InspectorService
from .ollama_client import InspectorOllama
from .checkpoint import CheckpointManager
from .report import ReportBuilder

__all__ = [
    "InspectorService",
    "InspectorOllama",
    "CheckpointManager",
    "ReportBuilder",
]
