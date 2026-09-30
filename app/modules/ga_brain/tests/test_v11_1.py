import json,tempfile
from pathlib import Path
from app.modules.ga_brain.core_types import IntentMode,IntentObject,ActionPlan,RunStatus
from app.modules.ga_brain.context_manager import ConversationContextManager
from app.modules.ga_brain.permission_gate import PermissionGate
from app.modules.ga_brain.tool_registry import ToolRegistry
from app.modules.ga_brain.requirement_validator import RequirementValidator
from app.modules.ga_brain.execution_manager import ExecutionManager
from app.modules.ga_brain.executor import ToolExecutor
from app.modules.ga_brain.verifier import ResultVerifier
from app.modules.ga_brain.reference_resolver import ReferenceResolver

PASSED=0

def ck(cond,name):
 global PASSED
 assert cond,name; PASSED+=1

def intent(mode,explicit=False,action=''):
 return IntentObject(IntentMode(mode),explicit_command=explicit,requested_action=action)

reg=ToolRegistry(); gate=PermissionGate(); req=RequirementValidator(); runs=ExecutionManager(); exe=ToolExecutor(reg,gate,req,runs,enabled=False); ver=ResultVerifier(reg)
# Permission bug: forbid bot must not block AI core action.
p=ActionPlan('maintenance','code_edit','run',fields={'backup_confirmed':True,'changes':'x'},files=['app/modules/ga_brain/service.py'])
i=intent('ACTION',True,'sửa AI Core')
active=[{'status':'ACTIVE','effect':'FORBID','rule':'không đụng bot','target':'bot'}]
ck(gate.constraints_allow(p,i,active)[0],'allow AI under bot forbid')
# actual bot target is blocked.
pbot=ActionPlan('maintenance','code_edit','run',fields={'backup_confirmed':True,'changes':'x'},files=['app/modules/tao_anh_ai/api.py'])
active2=[{'status':'ACTIVE','effect':'FORBID','rule':'không sửa bot','file_scope':'app/modules/tao_anh_ai'}]
ck(not gate.constraints_allow(pbot,i,active2)[0],'block bot')
# Constraint revoke/supersede.
with tempfile.TemporaryDirectory() as td:
 m=ConversationContextManager(Path(td)/'m.json'); a=m.add_constraint({'scope':'SESSION','effect':'FORBID','rule':'không sửa bot','target':'bot'}); ck(len(m.constraints())==1,'constraint add'); m.revoke_constraints({'target':'bot'}); ck(len(m.constraints())==0,'constraint revoke'); m.add_constraint({'scope':'SESSION','effect':'FORBID','rule':'x','target':'bot'}); b=m.add_constraint({'scope':'SESSION','effect':'ALLOW','rule':'cho phép bot','target':'bot'}); ck(len(m.constraints())==1 and m.constraints()[0]['effect']=='ALLOW','constraint supersede')
# Requirement validation (V11.2: physical state must be real, never planner booleans).
t=reg.get('code_edit')
with tempfile.TemporaryDirectory() as td:
 f=Path(td)/'x.py'; f.write_text('x=1\n',encoding='utf-8')
 p=ActionPlan('maintenance','code_edit','run',fields={'changes':'x'},files=[]); ok,reason=req.validate(t,p,{}); ck(not ok and reason=='missing_target','backup requirement needs real target')
 p=ActionPlan('maintenance','code_edit','run',fields={'changes':'x','path':str(f)},files=[str(f)]); ok,reason=req.validate(t,p,{}); ck(ok,'requirements pass on real target')
# Verifier no real evidence no success; claimed strings are ignored.
v=ver.verify_report({'status':'SUCCESS','evidence':[]},'code_edit'); ck(v.status==RunStatus.UNVERIFIED and not v.ok,'no evidence')
v=ver.verify_report({'status':'SUCCESS','evidence':['target_exists','write_confirmed','syntax_check','expected_change']},'code_edit'); ck(v.status==RunStatus.UNVERIFIED and not v.ok,'claimed evidence not trusted')
# Tool mismatch.
p=ActionPlan('aiimage','file_read','run'); ok,reason=gate.capability_allow(reg.get('file_read'),i,p); ck(not ok and reason=='tool_target_mismatch','tool mismatch')
# Non-action cannot authorize.
for mode in ['CHAT','QUESTION','ANALYZE']:
 p=ActionPlan('maintenance','code_edit','run',fields={'backup_confirmed':True,'changes':'x'}); ok,_=gate.authorize(intent(mode),p,{}); ck(not ok,f'{mode} no side effect')
# Action dry-run would authorize, still does not execute.
with tempfile.TemporaryDirectory() as td:
 f=Path(td)/'x.py'; f.write_text('x=1\n',encoding='utf-8')
 p=ActionPlan('maintenance','code_edit','run',fields={'path':str(f),'changes':'x'},files=[str(f)]); ex=exe.prepare(intent('ACTION',True,'sửa AI'),p,{'active_task':None},[]); ck(ex['would_authorize'] and not ex['authorized'] and ex['reason']=='core_only_phase_tools_locked','dry run lock')
# Continue requires active context.
p=ActionPlan('maintenance','code_edit','run',fields={'backup_confirmed':True,'changes':'x'}); ok,reason=gate.authorize(intent('CONTINUE'),p,{}); ck(not ok and reason=='no_active_task_to_continue','continue no context')
# Ambiguous references.
r=ReferenceResolver().resolve(IntentObject(IntentMode.ACTION,context_references=['nó'],explicit_command=True),{'references_map':{}}); ck(r['unresolved']==['nó'],'ambiguous unresolved')
r=ReferenceResolver().resolve(IntentObject(IntentMode.ACTION,context_references=['mấy lỗi đó'],explicit_command=True),{'last_identified_problems':['e1']}); ck(r['resolved']['mấy lỗi đó']==['e1'],'reference resolved')
# Cancel lifecycle.
p=ActionPlan('maintenance','code_edit','run'); eid=runs.create(p); c=runs.cancel(eid,None); ck(c['status']=='CANCEL_FAILED' and c['reason']=='cancel_not_supported','cancel unsupported truthful')
p2=ActionPlan('maintenance','code_edit','run'); eid2=runs.create(p2); c=runs.cancel(eid2,lambda _:True); ck(c['status']=='CANCELLED' and c['ok'],'cancel supported')
# execution ids separated.
ck(eid!=eid2,'execution ids unique')
# failure response remains failure.
v=ver.verify_report({'status':'FAILED','evidence':['x'],'error':'boom'},'code_edit'); ck(v.status==RunStatus.FAILED and not v.ok,'failed truthful')
print(json.dumps({'passed':PASSED,'failed':0,'skipped':0},ensure_ascii=False))
