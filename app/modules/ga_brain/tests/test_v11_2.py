import tempfile, json
from pathlib import Path
from app.modules.ga_brain.context_manager import ConversationContextManager
from app.modules.ga_brain.core_types import IntentMode,IntentObject,ActionPlan,RunStatus
from app.modules.ga_brain.permission_gate import PermissionGate
from app.modules.ga_brain.tool_registry import ToolRegistry
from app.modules.ga_brain.requirement_validator import RequirementValidator
from app.modules.ga_brain.execution_manager import ExecutionManager
from app.modules.ga_brain.executor import ToolExecutor
from app.modules.ga_brain.verifier import ResultVerifier
from app.modules.ga_brain.planner import Planner,PHYSICAL_ASSERTIONS

PASSED=0
def ck(v,name):
 global PASSED
 assert v,name; PASSED+=1

def action(): return IntentObject(IntentMode.ACTION,explicit_command=True,requested_action='sửa AI')

# 1. Scope lifecycle.
with tempfile.TemporaryDirectory() as td:
 m=ConversationContextManager(Path(td)/'m.json')
 a=m.add_constraint({'scope':'ACTION','effect':'FORBID','rule':'không bot','target':'bot','source_turn':7,'action_turn':7})
 ck(len(m.constraints(True,turn_id=7))==1,'action applies same turn')
 ck(len(m.constraints(True,turn_id=8))==0,'action does not leak next turn')
 ck(m.consume_action_constraints(7)==1 and len(m.constraints())==0,'action expires after use')
 t=m.add_constraint({'scope':'TASK','effect':'FORBID','rule':'không bot','target':'bot'})
 task=m.set_active_task({'message':'sửa AI','target':'maintenance','execution_id':'E1'})
 ck(len(m.constraints(True,task_id=task['task_id']))==1,'task binds')
 m.clear_active_task(); ck(len(m.constraints())==0,'task expires at task end')
 m.add_constraint({'scope':'SESSION','effect':'FORBID','rule':'không bot','target':'bot'})
 m.set_active_task({'message':'x','target':'maintenance','execution_id':'E2'}); m.clear_active_task()
 ck(len(m.constraints())==1,'session survives task')
 m.revoke_constraints({'target':'bot'}); ck(len(m.constraints())==0,'session revoke no zombie')

# 2. Permission scope and valid constraint target.
gate=PermissionGate(); p=ActionPlan('maintenance','code_edit','run',files=['app/modules/ga_brain/service.py'])
ctx={'current_turn_id':10,'active_task':None}
rule={'status':'ACTIVE','effect':'FORBID','scope':'ACTION','action_turn':9,'target':'maintenance'}
ck(gate.constraints_allow(p,action(),[rule],ctx)[0],'stale action constraint ignored')
rule['action_turn']=10
ck(not gate.constraints_allow(p,action(),[rule],ctx)[0],'current action constraint applies')

# 3. Planner strips fake physical assertions.
class FakeModel:
 def json(self,*a,**k):
  return {'tool_name':'code_edit','target':'maintenance','action':'run','fields':{'path':'x.py','backup_confirmed':True,'file_exists':True,'syntax_pass':True,'expected_contains':'X'},'files':['x.py'],'confidence':1}
reg=ToolRegistry(); pl=Planner(FakeModel(),reg)
pp,err=pl.build('sửa',action(),{})
ck(err is None and not (set(pp.fields)&PHYSICAL_ASSERTIONS),'planner physical claims stripped')

# 4. Requirement validator rejects injected physical claims and checks real file.
req=RequirementValidator(); tool=reg.get('code_edit')
with tempfile.TemporaryDirectory() as td:
 f=Path(td)/'a.py'; f.write_text('x=1\n',encoding='utf-8')
 bad=ActionPlan('maintenance','code_edit','run',fields={'path':str(f),'backup_confirmed':True,'changes':'x'},files=[str(f)])
 ok,reason=req.validate(tool,bad,{})
 ck(not ok and reason=='untrusted_physical_assertion','fake backup flag rejected')
 good=ActionPlan('maintenance','code_edit','run',fields={'path':str(f),'changes':'x'},files=[str(f)])
 ck(req.validate(tool,good,{})[0],'real existing target preflight passes')

# 5. Verifier ignores evidence strings; real filesystem facts required.
ver=ResultVerifier(reg); runs=ExecutionManager()
with tempfile.TemporaryDirectory() as td:
 f=Path(td)/'a.py'; f.write_text('x=1\n',encoding='utf-8')
 p=ActionPlan('maintenance','code_edit','run',fields={'path':str(f),'expected_contains':'x=2','changes':'x=2'},files=[str(f)])
 eid=runs.create(p); run=runs.get(eid)
 fake=ver.verify_report({'execution_id':eid,'status':'SUCCESS','evidence':['target_exists','write_confirmed','syntax_check','expected_change']},'code_edit',run)
 ck(fake.status==RunStatus.UNVERIFIED and not fake.ok,'fake evidence rejected')
 f.write_text('x=2\n',encoding='utf-8')
 real=ver.verify_report({'execution_id':eid,'status':'SUCCESS'},'code_edit',run)
 ck(real.status==RunStatus.SUCCESS and real.ok,'real write syntax expected change verified')
 ck(set(['target_exists','write_confirmed','syntax_check','expected_change']).issubset(set(real.evidence)),'real evidence labels produced by verifier')

# 6. Full dry-run pipeline permission: non-action never would_authorize.
exe=ToolExecutor(reg,gate,RequirementValidator(),ExecutionManager(),enabled=False)
for mode in (IntentMode.CHAT,IntentMode.QUESTION,IntentMode.ANALYZE,IntentMode.CANCEL):
 i=IntentObject(mode,explicit_command=False)
 p=ActionPlan('maintenance','file_write','run',fields={'path':'x','content':'y'},files=['x'])
 ex=exe.prepare(i,p,{'current_turn_id':1},[])
 ck(not ex['would_authorize'],f'{mode.value} full pipeline no authorization')

print(json.dumps({'suite':'v11.2_hardening','passed':PASSED,'failed':0,'skipped':0},ensure_ascii=False))
