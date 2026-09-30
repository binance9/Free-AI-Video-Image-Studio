from __future__ import annotations
import hashlib,py_compile,subprocess
from pathlib import Path
from .core_types import RunStatus,VerificationResult
class ResultVerifier:
    def __init__(self,registry=None): self.registry=registry
    def _hash(self,p):
        try:b=Path(p).read_bytes(); return hashlib.sha256(b).hexdigest()
        except Exception:return None
    def _syntax_check(self,p):
        q=Path(p)
        try:
            if q.suffix.lower()=='.py': py_compile.compile(str(q),doraise=True); return True
            if q.suffix.lower()=='.js': return subprocess.run(['node','--check',str(q)],capture_output=True,timeout=20).returncode==0
            if q.suffix.lower() in {'.json'}:
                import json; json.loads(q.read_text(encoding='utf-8')); return True
            return True
        except Exception:return False
    def _real_evidence(self,report,spec,run):
        ev=[]; run=run or {}; plan=(run.get('plan') or {}); pre=(run.get('pre_state') or {}).get('files',[]); premap={x.get('path'):x for x in pre if isinstance(x,dict)}
        locators=[]
        for x in list(plan.get('files') or []): locators.append(x)
        fp=(plan.get('fields') or {}).get('path')
        if fp:locators.append(fp)
        for key in ('artifact_path','output_path','path','file'):
            v=report.get(key)
            if isinstance(v,str) and v:locators.append(v)
        # locator is untrusted; existence/hash are checked here.
        checked=[]
        for raw in dict.fromkeys(locators):
            q=Path(raw)
            try: rp=str(q.resolve())
            except Exception: rp=str(q)
            exists=q.exists(); checked.append((q,rp,exists))
            if exists: ev.append('target_exists')
        if spec:
            if any('artifact_exists'==str(x).lower() for x in spec.required_evidence):
                if any(exists for _,_,exists in checked): ev.append('artifact_exists')
            if 'artifact_type_image' in [str(x).lower() for x in spec.required_evidence]:
                if any(exists and q.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} for q,_,exists in checked): ev.append('artifact_type_image')
            if 'artifact_type_3d' in [str(x).lower() for x in spec.required_evidence]:
                if any(exists and q.suffix.lower() in {'.glb','.gltf','.fbx','.obj','.blend'} for q,_,exists in checked): ev.append('artifact_type_3d')
        # Detect actual write by pre/post fingerprint difference.
        for q,rp,exists in checked:
            if not exists:continue
            before=premap.get(rp)
            after=self._hash(q)
            if before and before.get('exists') and after and after!=before.get('sha256'): ev.append('write_confirmed')
            elif before and not before.get('exists') and after: ev.append('write_confirmed')
            elif not before and after:
                # Output paths are only locators. Prove creation/update happened during this execution by filesystem mtime.
                try:
                    if run.get('created_at') and q.stat().st_mtime >= float(run.get('created_at'))-0.001: ev.append('write_confirmed')
                except Exception: pass
        # Syntax is run by verifier itself, never accepted from report strings.
        if checked and all(self._syntax_check(q) for q,_,exists in checked if exists): ev.append('syntax_check')
        # Expected change must be machine-checkable from plan.
        expected=(plan.get('fields') or {}).get('expected_contains')
        if expected and checked:
            try:
                if any(expected in q.read_text(encoding='utf-8') for q,_,exists in checked if exists): ev.append('expected_change')
            except Exception: pass
        return list(dict.fromkeys(ev))
    def verify_report(self,report,tool_name=None,run=None):
        report=report if isinstance(report,dict) else {}; raw=str(report.get('status') or '').upper(); eid=str(report.get('execution_id') or '')
        spec=self.registry.get(tool_name or report.get('tool_name')) if self.registry else None; evidence=self._real_evidence(report,spec,run)
        if raw in {'FAILED','ERROR'}:return VerificationResult(RunStatus.FAILED,False,evidence,str(report.get('error') or report.get('message') or 'Tool thất bại.'),eid)
        if raw=='CANCELLED':return VerificationResult(RunStatus.CANCELLED,False,evidence,'Execution đã hủy.',eid)
        if raw in {'PARTIAL','PARTIAL_SUCCESS'}:return VerificationResult(RunStatus.PARTIAL,False,evidence,'Kết quả mới đạt một phần.',eid)
        if raw in {'DONE','COMPLETED','SUCCESS','PASS'}:
            if not evidence:return VerificationResult(RunStatus.UNVERIFIED,False,[],'NO REAL EVIDENCE = NO VERIFIED SUCCESS',eid)
            if spec:
                missing=[x for x in spec.required_evidence if str(x).lower() not in [e.lower() for e in evidence]]
                if missing:return VerificationResult(RunStatus.UNVERIFIED,False,evidence,'Thiếu real evidence bắt buộc: '+', '.join(missing),eid)
            return VerificationResult(RunStatus.SUCCESS,True,evidence,'Đã verify SUCCESS bằng kiểm chứng hệ thống.',eid)
        return VerificationResult(RunStatus.RUNNING,False,evidence,'Chưa có bằng chứng hoàn thành.',eid)
