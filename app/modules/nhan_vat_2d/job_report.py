from __future__ import annotations
from pathlib import Path
import json

def write_report(path: str|Path, payload: dict) -> str:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return str(p)
