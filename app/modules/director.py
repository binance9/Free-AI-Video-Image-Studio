import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from app.modules.base import MODULES
from app.storage.project_memory import ProjectMemory

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
