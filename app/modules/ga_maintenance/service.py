from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "models", "model", "weights",
    "outputs", "output", "downloads", "download", "projects", "project", "data",
    "assets", "cache", ".cache", "temp", "tmp",
}

# These are exact files created by earlier Gà patch attempts, not app source.
KNOWN_OLD_FIX_FILES = {
    "FIX_GA_API_OFF_NOT_FOUND.bat",
    "FIX_GA_API_OFF_V2_FORCE_RESTART.bat",
    "FIX_GA_V3_DIRECT_BACKEND_AND_SHOW_ERROR.bat",
}

SUSPECT_NAMES = (
    ".bak", ".old", ".orig", ".copy", " copy.", "_old.", "_backup.", "~",
)


class SafeProjectAuditor:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _inside(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.root)
            return True
        except Exception:
            return False

    def _source_files(self, suffixes):
        for base_name in ("app", "web"):
            base = self.root / base_name
            if not base.is_dir():
                continue
            for p in base.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in suffixes:
                    continue
                rel = p.relative_to(self.root)
                if any(part.lower() in EXCLUDED_DIRS for part in rel.parts[:-1]):
                    continue
                yield p
        for p in self.root.iterdir():
            if p.is_file() and p.suffix.lower() in suffixes:
                yield p

    def _python_syntax(self):
        issues=[]; count=0
        for p in self._source_files({".py"}):
            count += 1
            try:
                text=p.read_text(encoding="utf-8-sig")
                ast.parse(text, filename=str(p))
            except Exception as exc:
                issues.append({"type":"python_syntax","file":str(p.relative_to(self.root)),"error":str(exc)})
        return count,issues

    def _js_syntax(self):
        files=list(self._source_files({".js"})); issues=[]
        node=shutil.which("node")
        if not node:
            return len(files), issues, "Node.js không có trong PATH: bỏ qua node --check, không tự đoán JS lỗi."
        for p in files:
            try:
                r=subprocess.run([node,"--check",str(p)],capture_output=True,text=True,timeout=12)
                if r.returncode:
                    issues.append({"type":"javascript_syntax","file":str(p.relative_to(self.root)),"error":(r.stderr or r.stdout).strip()[-2000:]})
            except Exception as exc:
                issues.append({"type":"javascript_check_error","file":str(p.relative_to(self.root)),"error":str(exc)})
        return len(files),issues,None

    def _json_syntax(self):
        issues=[]; count=0
        # Source JSON only. Never scan user/project data.
        for p in self._source_files({".json"}):
            count += 1
            try: json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as exc: issues.append({"type":"json_syntax","file":str(p.relative_to(self.root)),"error":str(exc)})
        return count,issues

    def _static_refs(self):
        idx=self.root/"web"/"index.html"; issues=[]; count=0
        if not idx.is_file():
            return count,[{"type":"missing_core_file","file":"web/index.html","error":"Không tồn tại"}]
        text=idx.read_text(encoding="utf-8-sig",errors="replace")
        for m in re.finditer(r'(?:src|href)=["\'](/static/[^"\'?]+)',text):
            count += 1
            rel=m.group(1)[len('/static/'):]
            p=self.root/"web"/rel
            if not p.is_file():
                issues.append({"type":"missing_static_ref","file":"web/index.html","error":f"Thiếu /static/{rel}"})
        return count,issues

    def _safe_garbage(self):
        safe=[]; suspect=[]
        # Regenerable byte-code caches only inside source/root.
        for base in [self.root, self.root/"app", self.root/"web"]:
            if not base.exists(): continue
            for p in base.rglob("__pycache__"):
                if p.is_dir() and self._inside(p):
                    rel=p.relative_to(self.root)
                    if not any(part.lower() in EXCLUDED_DIRS for part in rel.parts):
                        safe.append(p)
            for p in base.rglob("*"):
                if not p.is_file() or not self._inside(p): continue
                rel=p.relative_to(self.root)
                if any(part.lower() in EXCLUDED_DIRS for part in rel.parts[:-1]): continue
                low=p.name.lower()
                if p.suffix.lower() in {".pyc",".pyo"}:
                    safe.append(p)
                elif any(tok in low for tok in SUSPECT_NAMES):
                    suspect.append(str(rel))
        for name in KNOWN_OLD_FIX_FILES:
            p=self.root/name
            if p.is_file(): safe.append(p)
        # De-duplicate nested __pycache__ contents: directory deletion covers children.
        dirset={p.resolve() for p in safe if p.is_dir()}
        final=[]
        for p in safe:
            rp=p.resolve()
            if p.is_file() and any(d in rp.parents for d in dirset): continue
            if rp not in [x.resolve() for x in final]: final.append(p)
        return final, sorted(set(suspect))

    def _unreferenced_web(self):
        # Advisory only. Never auto-delete because modules can be loaded dynamically.
        idx=self.root/"web"/"index.html"
        if not idx.is_file(): return []
        text=idx.read_text(encoding="utf-8-sig",errors="replace")
        out=[]
        for p in (self.root/"web").rglob("*.js"):
            rel=p.relative_to(self.root/"web").as_posix()
            if f"/static/{rel}" not in text and p.name not in {"ga_brain.js","ga_owner.js"}:
                out.append("web/"+rel)
        return sorted(out)

    def audit(self, cleanup=True, repair=True):
        started=time.time(); issues=[]; notes=[]
        py_n,py_i=self._python_syntax(); issues += py_i
        js_n,js_i,js_note=self._js_syntax(); issues += js_i
        if js_note: notes.append(js_note)
        json_n,json_i=self._json_syntax(); issues += json_i
        ref_n,ref_i=self._static_refs(); issues += ref_i
        safe,suspect=self._safe_garbage()
        cleaned=[]; cleanup_errors=[]
        if cleanup:
            for p in sorted(safe,key=lambda x:len(x.parts),reverse=True):
                try:
                    if not self._inside(p):
                        raise RuntimeError("Refuse outside project root")
                    rel=str(p.relative_to(self.root))
                    if p.is_dir(): shutil.rmtree(p)
                    elif p.exists(): p.unlink()
                    cleaned.append(rel)
                except Exception as exc:
                    cleanup_errors.append({"file":str(p),"error":str(exc)})
        # Repair policy is intentionally conservative: only deterministic cleanup.
        # Existing app source is NEVER rewritten from a guess.
        repairable=[]
        for issue in issues:
            if issue["type"] in {"python_syntax","javascript_syntax","json_syntax","missing_static_ref"}:
                repairable.append(issue)
        if repair and repairable:
            notes.append(
                "Có lỗi source nhưng không có bản sửa xác định 100%. Gà KHÔNG tự ghi đè file; đã giữ nguyên và báo rõ để tránh sửa nhầm."
            )
        unused=self._unreferenced_web()
        if suspect or unused:
            notes.append("File nghi không dùng chỉ được liệt kê, KHÔNG tự xóa khi chưa chắc chắn.")
        return {
            "ok": not issues,
            "elapsed_seconds": round(time.time()-started,2),
            "checked": {"python":py_n,"javascript":js_n,"json":json_n,"static_refs":ref_n},
            "issues": issues,
            "cleaned_safe": cleaned,
            "cleanup_errors": cleanup_errors,
            "suspect_not_deleted": suspect[:80],
            "unreferenced_web_not_deleted": unused[:80],
            "notes": notes,
            "policy": {
                "auto_delete": "Chỉ cache bytecode và đúng tên FIX_GA cũ do Gà tạo.",
                "never_touch": "data/models/weights/output/projects/assets/.venv/node_modules",
                "uncertain": "Không xóa/không sửa; báo trong chat.",
            },
        }
