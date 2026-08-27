import json
from datetime import datetime, timezone
from typing import Any

from app.storage.database import Database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class ProjectMemory:
    def __init__(self, db: Database):
        self.db = db

    def save_project(self, project: dict[str, Any]) -> None:
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(id,name,command,status,current_stage,plan_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,
                  command=excluded.command,
                  status=excluded.status,
                  current_stage=excluded.current_stage,
                  plan_json=excluded.plan_json,
                  updated_at=excluded.updated_at
                """,
                (
                    project["id"], project["name"], project["command"],
                    project["status"], project["current_stage"],
                    json.dumps(project["plan"], ensure_ascii=False),
                    project.get("created_at", now), now,
                ),
            )

    def add_event(self, project_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO project_events(project_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
                (project_id, event_type, json.dumps(payload, ensure_ascii=False), utc_now()),
            )

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "name": row["name"], "command": row["command"],
            "status": row["status"], "current_stage": row["current_stage"],
            "plan": json.loads(row["plan_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_projects(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id FROM projects ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [p for r in rows if (p := self.get_project(r["id"]))]
