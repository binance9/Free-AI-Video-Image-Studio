import time,uuid,hashlib
from pathlib import Path
class ExecutionManager:
    def __init__(self): self._runs={}
    def _snapshot_file(self,p):
        try:
            q=Path(p); b=q.read_bytes(); return {'path':str(q.resolve()),'exists':True,'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'mtime_ns':q.stat().st_mtime_ns}
        except Exception:return {'path':str(p),'exists':False}
    def create(self,plan):
        eid=plan.execution_id or uuid.uuid4().hex; plan.execution_id=eid; files=list(plan.files or []); fp=(plan.fields or {}).get('path')
        if fp and fp not in files: files.append(fp)
        self._runs[eid]={'execution_id':eid,'status':'PLANNED','plan':plan.to_dict(),'created_at':time.time(),'pre_state':{'files':[self._snapshot_file(x) for x in files]}}; return eid
    def set(self,eid,status,**kw):
        if eid not in self._runs:return None
        self._runs[eid]['status']=status; self._runs[eid].update(kw); self._runs[eid]['updated_at']=time.time(); return dict(self._runs[eid])
    def get(self,eid):return dict(self._runs[eid]) if eid in self._runs else None
    def active(self):
        for x in reversed(list(self._runs.values())):
            if x.get('status') in {'PLANNED','RUNNING','CANCEL_REQUESTED'}:return dict(x)
        return None
    def cancel(self,eid=None,cancel_callback=None):
        run=self.get(eid) if eid else self.active()
        if not run:return {'ok':False,'reason':'no_active_execution'}
        eid=run['execution_id']; self.set(eid,'CANCEL_REQUESTED')
        if cancel_callback is None:self.set(eid,'CANCEL_FAILED',reason='cancel_not_supported'); return {'ok':False,'reason':'cancel_not_supported','execution_id':eid,'status':'CANCEL_FAILED'}
        try:
            ok=bool(cancel_callback(run)); self.set(eid,'CANCELLED' if ok else 'CANCEL_FAILED'); return {'ok':ok,'reason':'cancelled' if ok else 'cancel_failed','execution_id':eid,'status':'CANCELLED' if ok else 'CANCEL_FAILED'}
        except Exception as e:self.set(eid,'CANCEL_FAILED',reason=str(e)); return {'ok':False,'reason':'cancel_failed','execution_id':eid,'status':'CANCEL_FAILED'}
