from __future__ import annotations
import json,time,uuid
from pathlib import Path
from threading import RLock
from .core_types import ConstraintRule,ConstraintStatus

class ConversationContextManager:
    SCHEMA_VERSION=112
    def __init__(self,path:Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=RLock()
        self.data={'schema_version':self.SCHEMA_VERSION,'turns':[],'modules':{},'constraints':[],'session':{'references':{},'cancelled_tasks':[]}}
        self.load(); self._migrate()
    def load(self):
        if self.path.is_file():
            try:
                o=json.loads(self.path.read_text(encoding='utf-8')); self.data.update(o if isinstance(o,dict) else {})
            except Exception: pass
    def save(self): self.path.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8')
    def _migrate(self):
        with self.lock:
            oldver=int(self.data.get('schema_version') or 0)
            s=self.data.setdefault('session',{}); s.setdefault('references',{}); s.setdefault('cancelled_tasks',[])
            if oldver<111:
                old=self.data.get('current') if isinstance(self.data.get('current'),dict) else {}
                for k in ('topic','object','active_task','pending_action','file','image','last_result','last_analysis'):
                    if k in old and k not in s: s[k]=old[k]
                self.data['constraints']=[]; self.data.pop('active_goal',None); self.data.pop('pending_action',None)
            if oldver<112:
                # V11.2 does not keep ambiguous legacy ACTION/TASK constraints alive.
                for x in self.data.setdefault('constraints',[]):
                    if isinstance(x,dict) and x.get('status')=='ACTIVE' and str(x.get('scope','SESSION')).upper() in {'ACTION','TASK'}:
                        x['status']='EXPIRED'
                self.data['schema_version']=self.SCHEMA_VERSION; self.save()
    def add_turn(self,role,text,**kw):
        with self.lock:
            turns=self.data.setdefault('turns',[]); item={'role':str(role),'text':str(text),'at':time.time(),'turn_id':(turns[-1].get('turn_id',0)+1 if turns else 1)}; item.update({k:v for k,v in kw.items() if v is not None}); turns.append(item); del turns[:-80]; self.save(); return item['turn_id']
    def recent_turns(self,limit=20): return list(self.data.get('turns',[])[-max(1,int(limit)):])
    def add_chat(self,role,text): self.add_turn(role,text)
    def recent_chat(self,limit=10): return self.recent_turns(limit)
    def remember(self,module,settings,source='manual'):
        if isinstance(settings,dict): self.data.setdefault('modules',{})[str(module)]={'last':dict(settings),'source':source,'updated_at':time.time()}; self.save()
    def profile(self,module=None): return dict(self.data.get('modules',{}).get(module,{})) if module else dict(self.data)
    def session(self): return self.data.setdefault('session',{})
    def current(self): return dict(self.session())
    def update_session(self,**kw):
        s=self.session()
        for k,v in kw.items():
            if v is None: s.pop(k,None)
            else: s[k]=v
        s['updated_at']=time.time(); self.save()
    def active_task(self):
        t=self.session().get('active_task'); return dict(t) if isinstance(t,dict) else None
    def set_active_task(self,t):
        t=dict(t); t.setdefault('task_id',t.get('execution_id') or uuid.uuid4().hex)
        self.update_session(active_task=t,pending_action=None,current_target=t.get('target')); self.bind_pending_task_constraints(t['task_id']); return t
    def clear_active_task(self):
        old=self.active_task(); self.update_session(active_task=None,pending_action=None)
        if old: self.expire_task_constraints(old.get('task_id') or old.get('execution_id'))
    def get_goal(self): return self.active_task()
    def set_goal(self,message,target,requirements=None): self.set_active_task({'message':message,'target':target,'requirements':list(requirements or []),'at':time.time()})
    def clear_goal(self): self.clear_active_task()
    def get_pending(self):
        p=self.session().get('pending_action'); return dict(p) if isinstance(p,dict) else None
    def set_pending(self,message,target,requirements=None): self.update_session(pending_action={'message':message,'target':target,'requirements':list(requirements or []),'at':time.time()})
    def clear_pending(self): self.update_session(pending_action=None)
    def add_history(self,message,target): self.add_turn('system',f'ACTION_TARGET:{target}',meta={'message':message,'target':target})
    def constraints(self,active_only=True,turn_id=None,task_id=None):
        out=[]
        for x in self.data.get('constraints',[]):
            if not isinstance(x,dict): continue
            if active_only and x.get('status')!='ACTIVE': continue
            scope=str(x.get('scope') or 'SESSION').upper()
            if active_only and scope=='ACTION' and turn_id is not None and int(x.get('action_turn') or -1)!=int(turn_id): continue
            if active_only and scope=='TASK':
                rid=x.get('task_id')
                if rid and task_id and rid!=task_id: continue
                if rid and not task_id: continue
            out.append(dict(x))
        return out
    def _supersede(self,pred,new_id):
        for x in self.data.setdefault('constraints',[]):
            if x.get('status')=='ACTIVE' and pred(x): x['status']='SUPERSEDED'; x['superseded_by']=new_id
    def add_constraint(self,rule:dict):
        rid=rule.get('id') or uuid.uuid4().hex[:12]; scope=str(rule.get('scope') or 'SESSION').upper(); effect=str(rule.get('effect') or 'FORBID').upper(); target=rule.get('target'); tool=rule.get('tool'); file_scope=rule.get('file_scope')
        if scope not in {'SESSION','TASK','ACTION'}: scope='SESSION'
        def same_constraint_slot(x):
            if x.get('scope')!=scope:return False
            structured=any(v is not None for v in (target,tool,file_scope))
            if structured:return x.get('target')==target and x.get('tool')==tool and x.get('file_scope')==file_scope
            return (not any(x.get(k) is not None for k in ('target','tool','file_scope'))) and str(x.get('rule') or '').strip().lower()==str(rule.get('rule') or '').strip().lower()
        self._supersede(same_constraint_slot, rid)
        item=ConstraintRule(rid,scope,str(rule.get('rule') or ''),effect,target,tool,file_scope,time.time(),int(rule.get('source_turn') or 0),task_id=rule.get('task_id'),action_turn=rule.get('action_turn'),expires_after_use=(scope=='ACTION')).to_dict()
        if scope=='ACTION' and not item.get('action_turn'): item['action_turn']=int(rule.get('source_turn') or 0)
        self.data.setdefault('constraints',[]).append(item); self.save(); return item
    def bind_pending_task_constraints(self,task_id):
        changed=False
        for x in self.data.setdefault('constraints',[]):
            if x.get('status')=='ACTIVE' and x.get('scope')=='TASK' and not x.get('task_id'): x['task_id']=task_id; changed=True
        if changed:self.save()
    def consume_action_constraints(self,turn_id):
        n=0
        for x in self.data.setdefault('constraints',[]):
            if x.get('status')=='ACTIVE' and x.get('scope')=='ACTION' and int(x.get('action_turn') or -1)==int(turn_id): x['status']='EXPIRED'; n+=1
        if n:self.save()
        return n
    def expire_task_constraints(self,task_id):
        if not task_id:return 0
        n=0
        for x in self.data.setdefault('constraints',[]):
            if x.get('status')=='ACTIVE' and x.get('scope')=='TASK' and x.get('task_id')==task_id: x['status']='EXPIRED'; n+=1
        if n:self.save()
        return n
    def revoke_constraints(self,matcher:dict|None=None):
        matcher=matcher or {}; n=0
        for x in self.data.setdefault('constraints',[]):
            if x.get('status')!='ACTIVE': continue
            if all(v is None or x.get(k)==v for k,v in matcher.items()): x['status']='REVOKED'; n+=1
        self.save(); return n
    def clear_constraints(self): return self.revoke_constraints({})
    def remember_policy(self,text): self.add_constraint({'scope':'SESSION','rule':str(text),'effect':'FORBID' if 'không' in str(text).lower() or 'cấm' in str(text).lower() else 'ALLOW'})
    def policies(self): return [x.get('rule','') for x in self.constraints(True)]
    def snapshot(self,runtime_context=None):
        r=runtime_context if isinstance(runtime_context,dict) else {}; s=dict(self.session()); task=s.get('active_task') or {}; task_id=task.get('task_id') or task.get('execution_id')
        return {'recent_turns':self.recent_turns(20),'active_constraints':self.constraints(True,task_id=task_id),'active_topic':s.get('topic'),'active_task':s.get('active_task'),'current_target':s.get('current_target'),'current_files':s.get('current_files',[]),'current_artifact':s.get('artifact'),'current_image':r.get('attachment_name') or s.get('image'),'last_analysis':s.get('last_analysis'),'last_identified_problems':s.get('last_identified_problems',[]),'pending_plan':s.get('pending_plan'),'last_execution_result':s.get('last_result'),'cancelled_tasks':s.get('cancelled_tasks',[]),'references_map':s.get('references',{}),'current_module':r.get('current_module'),'has_video':bool(r.get('has_video')),'attachment':bool(r.get('attachment')),'runtime':r}
