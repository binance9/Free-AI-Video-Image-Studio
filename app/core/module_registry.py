"""Catalog of the conceptual engines/modules in AI Video Factory, and the
DirectorAI that bootstraps a new project from a free-text command against
that catalog. Not a feature module itself - lives in app/core.

Note: MODULES below is a forward-looking roadmap catalog (script, character,
storyboard, video, voice, lipsync, translation, subtitle, editor, quality,
memory, cost, provider) - only a subset have real implementations today
(character -> nhan_vat_2d/nhan_vat_3d, editor -> chinh_sua_video,
translation/subtitle -> phu_de). It is not an enforced registry of actual
running modules.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.storage.project_memory import ProjectMemory


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    label: str
    responsibility: str


MODULES = [
    ModuleDefinition("script", "Script Engine", "Viết và chuẩn hóa kịch bản"),
    ModuleDefinition("character", "Character Engine", "Tạo và giữ nhất quán nhân vật"),
    ModuleDefinition("storyboard", "Storyboard Engine", "Chia cảnh, shot và prompt hình ảnh"),
    ModuleDefinition("video", "Video Engine", "Điều phối sinh video qua provider/local model"),
    ModuleDefinition("voice", "Voice Engine", "Giọng đọc, hội thoại và voice identity"),
    ModuleDefinition("lipsync", "Lip-sync Engine", "Đồng bộ khẩu hình"),
    ModuleDefinition("translation", "Translation Engine", "Dịch đa ngôn ngữ"),
    ModuleDefinition("subtitle", "Subtitle Engine", "Tạo và căn thời gian phụ đề"),
    ModuleDefinition("editor", "Editor Engine", "Ghép shot, âm thanh, chuyển cảnh và render"),
    ModuleDefinition("quality", "Quality Control", "Chấm chất lượng và yêu cầu retry"),
    ModuleDefinition("memory", "Project Memory", "Lưu trạng thái, nhân vật, quyết định và lịch sử"),
    ModuleDefinition("cost", "Cost Controller", "Theo dõi ngân sách và chọn phương án tối ưu"),
    ModuleDefinition("provider", "Provider Manager", "Trừu tượng hóa API/model để thay thế dễ dàng"),
]


class DirectorAI:
    def __init__(self, memory: ProjectMemory):
        self.memory = memory

    @staticmethod
    def _name_from_command(command: str) -> str:
        text = re.sub(r"\s+", " ", command.strip())
        return (text[:52] + "…") if len(text) > 52 else text

    def create_project(self, command: str) -> dict:
        command = command.strip()
        if len(command) < 3:
            raise ValueError("Lệnh phải có ít nhất 3 ký tự")

        project_id = f"avf_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        plan = {
            "director_decision": "Khởi tạo pipeline tiêu chuẩn và giữ từng engine độc lập",
            "pipeline": [m.key for m in MODULES],
            "modules": [asdict(m) for m in MODULES],
            "next_action": "script",
        }
        project = {
            "id": project_id,
            "name": self._name_from_command(command),
            "command": command,
            "status": "READY",
            "current_stage": "director",
            "plan": plan,
            "created_at": now,
            "updated_at": now,
        }
        self.memory.save_project(project)
        self.memory.add_event(project_id, "PROJECT_CREATED", {"command": command})
        self.memory.add_event(project_id, "DIRECTOR_PLAN_CREATED", plan)
        return self.memory.get_project(project_id)
