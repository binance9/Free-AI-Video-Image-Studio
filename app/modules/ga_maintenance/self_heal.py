from __future__ import annotations

import difflib
import gc
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from app.core.job_log_broker import job_log_broker
from app.modules.ga_brain.model_client import OllamaClient
from .service import SafeProjectAuditor, EXCLUDED_DIRS


# Deep-diagnosis LLM call for job failures _classify() doesn't recognize. Only
# reasons from the traceback + the real file content it is given - never
# invents code it wasn't shown, and never claims a fix has been tested (that
# is always verified for real by _test_source, not asserted by the model).
DIAGNOSIS_SYSTEM = """
Mày là kỹ sư chẩn đoán lỗi runtime cho AI Video Factory. Owner đưa traceback/log lỗi
thật của một job, cộng với TOÀN BỘ nội dung hiện tại của đúng 1 file source bị traceback
chỉ tới. Nhiệm vụ: giải thích NGUYÊN NHÂN GỐC bằng tiếng Việt ngắn gọn, dựa đúng vào
nội dung file được cung cấp - không suy đoán code không có trong đó, không bịa tên
hàm/biến không xuất hiện trong file.

Chỉ đề xuất bản vá (new_content) khi mày THẬT SỰ chắc chắn: lỗi rõ ràng nằm trong chính
file này, bản sửa nhỏ gọn, không đổi hành vi nào khác ngoài đúng phạm vi lỗi. Nếu không
đủ chắc, để new_content=null và safe_to_patch=false - tuyệt đối không sửa mò.

new_content nếu có PHẢI là toàn bộ nội dung file sau khi sửa (không phải diff, không
phải đoạn trích) - giữ nguyên 100% phần không liên quan tới lỗi.

Không được tự nhận file đã qua test/đã pass - việc kiểm chứng luôn do hệ thống khác làm
sau khi mày trả lời, không phải việc của mày.

Trả đúng JSON schema:
{"diagnosis":"","confidence":0.0,"safe_to_patch":false,"new_content":null}
"""


SAFE_SOURCE_SUFFIXES = {".py", ".js", ".json", ".html", ".css"}
TERMINAL = {"done", "completed", "error", "failed", "cancelled", "partial_success"}
JOB_SCOPES = {"image", "character_2d", "character_3d", "object_3d", "map_hd", "video_cleanup", "facebook_video", "web_video"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


class LastKnownGood:
    """A read-only baseline captured only when the source passes static checks.

    It is used for deterministic rollback, never as proof that arbitrary logic is correct.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.store = self.root / "data" / "ga_maintenance" / "lkg"
        self.source = self.store / "source"
        self.manifest_path = self.store / "manifest.json"

    def _iter_source(self):
        for base_name in ("app", "web"):
            base = self.root / base_name
            if not base.is_dir():
                continue
            for p in base.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in SAFE_SOURCE_SUFFIXES:
                    continue
                rel = p.relative_to(self.root)
                if any(part.lower() in EXCLUDED_DIRS for part in rel.parts[:-1]):
                    continue
                yield p
        for name in ("START_VIDEO_FACTORY.py", "requirements.txt"):
            p = self.root / name
            if p.is_file():
                yield p

    def manifest(self) -> dict:
        if not self.manifest_path.is_file():
            return {}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def ensure(self) -> dict:
        current = self.manifest()
        if current.get("files") and self.source.is_dir():
            return {"ok": True, "created": False, "files": len(current["files"]), "created_at": current.get("created_at")}

        audit = SafeProjectAuditor(self.root).audit(cleanup=False, repair=False)
        if not audit.get("ok"):
            return {"ok": False, "created": False, "reason": "Source chưa sạch nên không tạo Last Known Good.", "issues": audit.get("issues", [])[:20]}

        tmp = self.store.with_name("lkg_building")
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        tmp_source = tmp / "source"
        tmp_source.mkdir(parents=True, exist_ok=True)
        files = {}
        for p in self._iter_source():
            rel = p.relative_to(self.root).as_posix()
            dst = tmp_source / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            files[rel] = {"sha256": _sha256(p), "size": p.stat().st_size}
        manifest = {"version": 1, "created_at": time.time(), "files": files}
        (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if self.store.exists():
            shutil.rmtree(self.store, ignore_errors=True)
        tmp.replace(self.store)
        return {"ok": True, "created": True, "files": len(files), "created_at": manifest["created_at"]}

    def info(self, rel: str) -> dict | None:
        return self.manifest().get("files", {}).get(rel)

    def baseline_file(self, rel: str) -> Path:
        return self.source / Path(rel)


class RuntimeSelfHealer:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.data_dir = self.root / "data" / "ga_maintenance"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lkg = LastKnownGood(self.root)
        self.restart_marker = self.data_dir / "restart.request"
        self.model_client = OllamaClient()
        # In-memory only, one-shot: never persisted, never re-appliable after
        # a restart or after being consumed once - matches ExecutionManager's
        # existing in-memory-only pattern elsewhere in this codebase.
        self._pending_patches: dict[str, dict] = {}

    def status(self):
        lkg = self.lkg.ensure()
        return {
            "ok": True,
            "mode": "safe-runtime-self-heal-v1",
            "last_known_good": lkg,
            "policy": {
                "auto_code_repair": "Chỉ rollback đúng file có LKG đã PASS và file hiện tại đã thay đổi; không viết code đoán.",
                "runtime_logic_unknown": "Không sửa nếu không có bằng chứng chắc chắn; báo file/dòng/lỗi trong chat.",
                "oom": "Dọn cache an toàn + unload Ollama; job do Gà tạo được retry tối đa 1 lần sau khi job cũ đã terminal.",
                "tests_before_restart": True,
            },
        }

    def _inside_source(self, path: Path) -> tuple[bool, str | None]:
        try:
            rp = path.resolve()
            rel = rp.relative_to(self.root)
        except Exception:
            return False, None
        if not rel.parts:
            return False, None
        if rel.parts[0] not in {"app", "web"} and rel.as_posix() != "START_VIDEO_FACTORY.py":
            return False, None
        if any(part.lower() in EXCLUDED_DIRS for part in rel.parts[:-1]):
            return False, None
        if rp.suffix.lower() not in SAFE_SOURCE_SUFFIXES and rel.as_posix() != "START_VIDEO_FACTORY.py":
            return False, None
        return True, rel.as_posix()

    def _resolve_trace_path(self, raw: str) -> Path | None:
        p = Path(raw)
        if p.is_absolute():
            return p
        candidate = (self.root / p).resolve()
        return candidate

    def _frames(self, text: str) -> list[dict]:
        frames = []
        # Python tracebacks: File "...", line N, in func
        for m in re.finditer(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\r\n]+))?', text):
            raw, line, func = m.group(1), int(m.group(2)), (m.group(3) or "").strip()
            p = self._resolve_trace_path(raw)
            if p is None:
                continue
            ok, rel = self._inside_source(p)
            if ok:
                frames.append({"file": rel, "line": line, "function": func})
        return frames

    @staticmethod
    def _classify(text: str) -> dict:
        low = text.lower()
        if "forrtl" in low and ("window-close event" in low or "error (200)" in low):
            return {
                "kind": "windows_console_close",
                "summary": "Hunyuan/Intel native runtime bị Windows gửi sự kiện đóng console (forrtl error 200).",
            }
        if any(k in low for k in ("cuda out of memory", "outofmemoryerror", "out of memory", "cublas_status_alloc_failed", "not enough memory")):
            return {"kind": "resource_oom", "summary": "Thiếu VRAM/RAM hoặc CUDA allocation thất bại."}
        if "modulenotfounderror" in low or "no module named" in low:
            return {"kind": "missing_dependency", "summary": "Thiếu module/dependency Python."}
        if "filenotfounderror" in low or "no such file or directory" in low or "the system cannot find the file" in low:
            return {"kind": "missing_file", "summary": "Pipeline đang thiếu file/đường dẫn đầu vào hoặc file runtime."}
        if "indentationerror" in low or "taberror" in low or "syntaxerror" in low:
            return {"kind": "syntax", "summary": "Lỗi cú pháp/indentation trong source."}
        if "jsondecodeerror" in low:
            return {"kind": "json", "summary": "JSON không hợp lệ."}
        if "nameerror" in low:
            return {"kind": "name_error", "summary": "Code gọi tên/biến chưa tồn tại."}
        if "attributeerror" in low:
            return {"kind": "attribute_error", "summary": "Code gọi thuộc tính/hàm không tồn tại trên object hiện tại."}
        if "typeerror" in low:
            return {"kind": "type_error", "summary": "Sai kiểu hoặc chữ ký hàm tại runtime."}
        if "connectionrefusederror" in low or "connection refused" in low:
            return {"kind": "connection", "summary": "Dịch vụ phụ trợ không nhận kết nối."}
        if "timeout" in low or "timed out" in low:
            return {"kind": "timeout", "summary": "Một bước hoặc dịch vụ phụ trợ bị timeout."}
        if "permissionerror" in low or "access is denied" in low or "permission denied" in low:
            return {"kind": "permission", "summary": "Windows từ chối quyền truy cập file/process."}
        return {"kind": "runtime", "summary": "Lỗi runtime chưa thuộc nhóm sửa tự động an toàn."}

    def collect_job_evidence(self, scope: str, job_id: str, job_state: dict | None = None) -> dict:
        if scope not in JOB_SCOPES:
            raise ValueError("scope log không hợp lệ")
        events = job_log_broker.after(scope, job_id, 0)
        useful = [e for e in events if e.get("level") in {"error", "warning"} or e.get("channel") == "stderr"]
        tail = useful[-120:] if useful else events[-120:]
        pieces = [str(e.get("message") or "") for e in tail]
        if isinstance(job_state, dict):
            for k in ("error", "detail", "message", "stage"):
                if job_state.get(k):
                    pieces.append(str(job_state[k]))
        text = "\n".join(x for x in pieces if x).strip()
        cls = self._classify(text)
        frames = self._frames(text)
        return {
            "scope": scope,
            "job_id": job_id,
            "classification": cls,
            "frames": frames[-12:],
            "error_text": text[-16000:],
            "events": tail[-30:],
        }

    def _quarantine(self, rel: str) -> Path:
        q = self.data_dir / "quarantine" / f"{_now_tag()}_{time.time_ns()}" / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        return q

    def _test_source(self, target_rel: str) -> dict:
        commands = []
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        target = self.root / target_rel

        if target.suffix.lower() == ".py":
            commands.append([sys.executable, "-m", "py_compile", str(target)])
            commands.append([sys.executable, "-m", "compileall", "-q", "app"])
            # Newer FastAPI wraps included routers in _IncludedRouter, which has no
            # top-level .path - app.routes alone silently under-collects paths and
            # this assertion previously always failed, reverting every candidate
            # fix regardless of correctness. Recurse into .original_router too.
            smoke = (
                "import app.main\n"
                "p=set()\n"
                "for r in app.main.app.routes:\n"
                "    orig=getattr(r,'original_router',None)\n"
                "    if orig is not None:\n"
                "        for sub in getattr(orig,'routes',[]):\n"
                "            sp=getattr(sub,'path',None)\n"
                "            if sp: p.add(sp)\n"
                "    rp=getattr(r,'path',None)\n"
                "    if rp: p.add(rp)\n"
                "assert '/api/health' in p; assert '/api/ga-brain/status' in p\n"
                "assert '/api/ga-maintenance/status' in p; print('APP_SMOKE_PASS')"
            )
            commands.append([sys.executable, "-c", smoke])
        elif target.suffix.lower() == ".js":
            node = shutil.which("node")
            if node:
                commands.append([node, "--check", str(target)])
        elif target.suffix.lower() == ".json":
            commands.append([sys.executable, "-c", f"import json; json.load(open({str(target)!r}, encoding='utf-8-sig')); print('JSON_PASS')"])

        results = []
        for cmd in commands:
            try:
                r = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True, timeout=90)
                results.append({"cmd": cmd, "returncode": r.returncode, "stdout": r.stdout[-3000:], "stderr": r.stderr[-5000:]})
                if r.returncode != 0:
                    return {"ok": False, "results": results}
            except Exception as exc:
                results.append({"cmd": cmd, "returncode": -1, "stderr": str(exc)})
                return {"ok": False, "results": results}

        audit = SafeProjectAuditor(self.root).audit(cleanup=False, repair=False)
        results.append({"static_audit_ok": audit.get("ok"), "issues": audit.get("issues", [])[:20]})
        return {"ok": bool(audit.get("ok")), "results": results}

    def _apply_and_verify(self, rel: str, new_text: str, restart_reason: str) -> dict:
        """Shared quarantine -> write -> test -> revert-on-fail transaction.

        Used by LKG rollback, the hardcoded console-close patch, and any
        LLM-proposed patch. PASS keeps the new content and requests a restart;
        FAIL restores exactly what was on disk before this call - a candidate
        write is never left half-applied."""
        current = self.root / rel
        q = None
        if current.is_file():
            q = self._quarantine(rel)
            shutil.copy2(current, q)
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text(new_text, encoding="utf-8")

        tests = self._test_source(rel)
        if tests.get("ok"):
            self.restart_marker.write_text(json.dumps({"reason": restart_reason, "file": rel, "at": time.time()}), encoding="utf-8")
            return {"fixed": True, "file": rel, "backup": str(q.relative_to(self.root)) if q else None, "tests": tests, "restart_required": True}

        # Transaction failed -> restore the broken/current version exactly as it was.
        if q and q.is_file():
            shutil.copy2(q, current)
        elif not q:
            current.unlink(missing_ok=True)
        return {"fixed": False, "reason": "Bản vá không qua test; đã hoàn tác.", "tests": tests}

    def _restore_lkg_if_changed(self, rel: str) -> dict:
        self.lkg.ensure()
        info = self.lkg.info(rel)
        baseline = self.lkg.baseline_file(rel)
        current = self.root / rel
        if not info or not baseline.is_file():
            return {"fixed": False, "reason": "Không có Last Known Good cho file này."}
        if current.is_file():
            current_hash = _sha256(current)
            if current_hash == info.get("sha256"):
                return {"fixed": False, "reason": "File đang giống Last Known Good; rollback không thể sửa lỗi logic hiện có."}
        return self._apply_and_verify(rel, baseline.read_text(encoding="utf-8"), "self_heal")


    def repair_character_hd_console_close(self) -> dict:
        rel = "app/modules/nhan_vat_3d/character_hd_backend.py"
        path = self.root / rel
        if not path.is_file():
            return {"fixed": False, "reason": f"Thiếu {rel}; không tự tạo file đoán."}

        text = path.read_text(encoding="utf-8")
        if "def _windows_creationflags()" in text and text.count("creationflags=self._windows_creationflags()") >= 2:
            return {
                "fixed": False,
                "already_fixed": True,
                "reason": "Character HD worker đã được cô lập khỏi console Windows bằng CREATE_NO_WINDOW.",
            }

        paint_marker = '        proc = subprocess.Popen(\n            cmd, cwd=str(self.tool_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,\n            text=True, encoding="utf-8", errors="replace", bufsize=1,\n        )\n'
        gen_marker = '        proc = subprocess.Popen(\n            cmd,\n            cwd=str(self.tool_dir),\n            env=env,\n            stdout=subprocess.PIPE,\n            stderr=subprocess.STDOUT,\n            text=True,\n            encoding="utf-8",\n            errors="replace",\n            bufsize=1,\n        )\n'
        helper_anchor = '    @property\n    def python(self) -> Path:\n'
        if paint_marker not in text or gen_marker not in text or helper_anchor not in text:
            return {"fixed": False, "reason": "Source Character HD không còn đúng cấu trúc đã kiểm chứng; tao không sửa mò."}

        helper = '    @staticmethod\n    def _windows_creationflags() -> int:\n        """Cô lập Hunyuan native worker khỏi console cha trên Windows."""\n        if os.name != "nt":\n            return 0\n        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))\n\n'
        patched = text.replace(helper_anchor, helper + helper_anchor, 1)
        patched = patched.replace(
            paint_marker,
            '        proc = subprocess.Popen(\n            cmd, cwd=str(self.tool_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,\n            text=True, encoding="utf-8", errors="replace", bufsize=1,\n            creationflags=self._windows_creationflags(),\n        )\n',
            1,
        )
        patched = patched.replace(
            gen_marker,
            '        proc = subprocess.Popen(\n            cmd,\n            cwd=str(self.tool_dir),\n            env=env,\n            stdout=subprocess.PIPE,\n            stderr=subprocess.STDOUT,\n            text=True,\n            encoding="utf-8",\n            errors="replace",\n            bufsize=1,\n            creationflags=self._windows_creationflags(),\n        )\n',
            1,
        )

        return self._apply_and_verify(rel, patched, "forrtl_window_close_fix")

    def recover_resources(self) -> dict:
        actions = []
        try:
            payload = json.dumps({"model": "qwen3:8b", "prompt": "", "keep_alive": 0, "stream": False}).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=4) as r:
                r.read(1024)
            actions.append("Đã yêu cầu Ollama nhả qwen3:8b khỏi RAM/VRAM.")
        except Exception:
            actions.append("Ollama không phản hồi lệnh unload; bỏ qua, không coi là lỗi repair.")
        gc.collect()
        actions.append("Đã chạy Python GC.")
        torch = sys.modules.get("torch")
        if torch is not None:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    actions.append("Đã empty CUDA cache an toàn.")
            except Exception as exc:
                actions.append(f"Không empty CUDA cache được: {exc}")
        return {"ok": True, "actions": actions}


    def preflight_repair(self) -> dict:
        """Repair deterministic static breakage before uvicorn imports the app.

        Only files that differ from an existing LKG are eligible.
        """
        audit = SafeProjectAuditor(self.root).audit(cleanup=False, repair=False)
        if audit.get("ok"):
            self.lkg.ensure()
            return {"ok": True, "fixed": [], "issues": []}
        fixed = []
        attempts = []
        for issue in audit.get("issues", []):
            if issue.get("type") not in {"python_syntax", "javascript_syntax", "json_syntax"}:
                continue
            rel = str(issue.get("file") or "")
            if not rel:
                continue
            result = self._restore_lkg_if_changed(rel)
            attempts.append({"file": rel, "result": result})
            if result.get("fixed"):
                fixed.append(rel)
        after = SafeProjectAuditor(self.root).audit(cleanup=False, repair=False)
        return {"ok": bool(after.get("ok")), "fixed": fixed, "issues": after.get("issues", []), "attempts": attempts}

    def _llm_diagnose(self, evidence: dict, target: str | None) -> dict | None:
        if not target:
            return None
        path = self.root / target
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None
        if len(content) > 12000:
            return {"diagnosis": "File quá lớn để tự đề xuất bản vá toàn file an toàn trong 1 lần gọi; cần xem tay.", "file": target}
        frame_line = (evidence.get("frames") or [{}])[-1].get("line")
        packet = {
            "error_text": evidence.get("error_text", "")[-4000:],
            "target_file": target,
            "target_line": frame_line,
            "file_content": content,
        }
        messages = [
            {"role": "system", "content": DIAGNOSIS_SYSTEM},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
        ]
        num_predict = min(6000, max(2400, len(content) // 3 + 1200))
        try:
            obj = self.model_client.json(messages, fast=False, deep=True, num_predict_override=num_predict)
        except Exception as exc:
            return {"diagnosis": f"Chẩn đoán LLM thất bại: {exc}", "file": target}
        if not isinstance(obj, dict):
            return {"diagnosis": "LLM không trả JSON hợp lệ cho chẩn đoán.", "file": target}
        diagnosis = str(obj.get("diagnosis") or "").strip()
        confidence = float(obj.get("confidence") or 0.0)
        safe = bool(obj.get("safe_to_patch")) and confidence >= 0.75
        new_content = obj.get("new_content") if safe else None
        if not isinstance(new_content, str) or not new_content.strip() or new_content == content:
            new_content = None
        return {"diagnosis": diagnosis, "confidence": confidence, "file": target, "old_content": content, "new_content": new_content}

    def apply_pending_patch(self, patch_id: str) -> dict:
        entry = self._pending_patches.pop(str(patch_id or ""), None)
        if not entry:
            return {"ok": False, "reason": "patch_not_found_or_already_used"}
        result = self._apply_and_verify(entry["file"], entry["new_content"], "llm_diagnosis_patch")
        return {"ok": True, **result}

    def heal_job(self, scope: str, job_id: str, job_state: dict | None = None) -> dict:
        evidence = self.collect_job_evidence(scope, job_id, job_state)
        cls = evidence["classification"]
        frames = evidence["frames"]
        messages = [f"Đã đọc log stderr/PowerShell của job {job_id[:8]} · {cls['summary']}"]

        if cls["kind"] == "windows_console_close":
            messages.append("Đây không phải lỗi ảnh/prompt. Hunyuan native worker bị dính sự kiện đóng console Windows.")
            result = self.repair_character_hd_console_close()
            if result.get("fixed"):
                messages.append("Đã backup file cũ và vá đúng 2 subprocess Hunyuan bằng CREATE_NO_WINDOW.")
                messages.append("Đã test source lại; chỉ khi PASS mới giữ bản sửa và yêu cầu restart backend.")
                return {"ok": True, "fixed": True, "classification": cls, "messages": messages, "evidence": evidence, **result}
            messages.append(result.get("reason") or "Không có repair an toàn.")
            if result.get("already_fixed"):
                messages.append("Fix chống window-CLOSE đã có sẵn nên tao không sửa tiếp bừa.")
            return {"ok": True, "fixed": False, "classification": cls, "messages": messages, "evidence": evidence, "manual_review_required": True}

        if cls["kind"] == "resource_oom":
            recovery = self.recover_resources()
            messages += recovery["actions"]
            messages.append("Job cũ đã lỗi/terminal thì có thể retry đúng 1 lần; không sửa source vì đây là lỗi tài nguyên.")
            return {"ok": True, "fixed": False, "resource_recovered": True, "retry_safe": True, "classification": cls, "messages": messages, "evidence": evidence}

        # Deterministic source rollback only when the traceback identifies a project source file.
        target = frames[-1]["file"] if frames else None
        if target:
            messages.append(f"Traceback chỉ tới {target}:{frames[-1]['line']}.")
            result = self._restore_lkg_if_changed(target)
            if result.get("fixed"):
                messages.append(f"File này đã khác Last Known Good. Tao đã backup bản lỗi, restore đúng bản PASS và chạy test lại: PASS.")
                messages.append("Cần mở lại AI Video Factory một lần để nạp code đã sửa; không tự restart Windows.")
                return {"ok": True, "fixed": True, "classification": cls, "messages": messages, "evidence": evidence, **result}
            messages.append(result.get("reason") or "Không có repair xác định 100%.")
            if result.get("tests"):
                messages.append("Repair thử không PASS nên đã hoàn tác, không để source ở trạng thái nửa vời.")
        else:
            messages.append("Log không chỉ ra một file source cụ thể đủ chắc để tự sửa.")

        if cls["kind"] == "missing_dependency":
            messages.append("Tao không tự pip install bừa vì launcher có thể dùng Python/venv khác. Cần xác nhận đúng interpreter trước.")
        elif cls["kind"] == "missing_file":
            messages.append("Tao không tự tạo/xóa file đầu vào khi chưa biết đó là asset tạm hay dữ liệu thật.")
        elif cls["kind"] in {"name_error", "attribute_error", "type_error", "runtime"}:
            messages.append("Đây là lỗi logic runtime. Nếu file không khác bản LKG thì không có bản sửa chắc chắn để tự ghi đè; tao giữ nguyên và báo mày thay vì sửa mò.")
        elif cls["kind"] in {"timeout", "connection", "permission"}:
            messages.append("Đây chưa chứng minh source sai; tao không sửa code khi nguyên nhân có thể là dịch vụ/quyền/timeout.")

        diag = self._llm_diagnose(evidence, target)
        if diag:
            if diag.get("diagnosis"):
                messages.append(f"Chẩn đoán sâu (LLM, đọc đúng file thật): {diag['diagnosis']}")
            if diag.get("new_content"):
                patch_id = uuid.uuid4().hex[:12]
                diff_text = "\n".join(difflib.unified_diff(
                    diag["old_content"].splitlines(), diag["new_content"].splitlines(),
                    fromfile=diag["file"], tofile=diag["file"] + " (đề xuất)", lineterm="",
                ))
                self._pending_patches[patch_id] = {
                    "file": diag["file"], "new_content": diag["new_content"], "created_at": time.time(),
                }
                messages.append(f"Đã có bản vá đề xuất cho {diag['file']} (chưa ghi gì cả).")
                messages.append(f"Gõ đúng: /apply-patch {patch_id} để tao ghi bản vá này. Gõ gì khác thì bản vá bị bỏ.")
                return {
                    "ok": True, "fixed": False, "classification": cls, "messages": messages, "evidence": evidence,
                    "manual_review_required": True,
                    "proposed_patch": {"patch_id": patch_id, "file": diag["file"], "diff": diff_text, "confidence": diag.get("confidence")},
                }

        return {"ok": True, "fixed": False, "classification": cls, "messages": messages, "evidence": evidence, "manual_review_required": True}
