import json, tempfile
from pathlib import Path
from app.modules.ga_brain.core_types import IntentMode, IntentObject, ActionPlan
from app.modules.ga_brain.execution_manager import ExecutionManager
from app.modules.ga_brain.permission_gate import PermissionGate
from app.modules.ga_brain.requirement_validator import RequirementValidator
from app.modules.ga_brain.executor import ToolExecutor
from app.modules.ga_brain.tool_registry import ToolRegistry
from app.modules.ga_brain.context_manager import ConversationContextManager
from app.modules.ga_brain.reference_resolver import ReferenceResolver

PASSED=0
def ck(v,name):
    global PASSED
    assert v,name; PASSED+=1

# 1) Unauthorized metric semantics: only CHAT/QUESTION/ANALYZE are non-action safety denominator.
SIDE_EFFECT_UNAUTHORIZED_MODES={IntentMode.CHAT,IntentMode.QUESTION,IntentMode.ANALYZE}
ck(IntentMode.ACTION not in SIDE_EFFECT_UNAUTHORIZED_MODES,'ACTION excluded from unauthorized denominator')
ck(IntentMode.CONTINUE not in SIDE_EFFECT_UNAUTHORIZED_MODES,'CONTINUE excluded from unauthorized denominator')
ck(IntentMode.CANCEL not in SIDE_EFFECT_UNAUTHORIZED_MODES,'CANCEL separate lifecycle')

# Full dry-run gate proves these three cannot authorize.
reg=ToolRegistry(); gate=PermissionGate(); exe=ToolExecutor(reg,gate,RequirementValidator(),ExecutionManager(),enabled=False)
for mode in SIDE_EFFECT_UNAUTHORIZED_MODES:
    intent=IntentObject(mode,explicit_command=False)
    plan=ActionPlan('maintenance','file_write','run',fields={'path':'x','content':'y'},files=['x'])
    result=exe.prepare(intent,plan,{'current_turn_id':1},[])
    ck(result['would_authorize'] is False,f'{mode.value} cannot would_authorize')

# ACTION may authorize in dry-run with valid requirements.
with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'a.txt'; f.write_text('old',encoding='utf-8')
    i=IntentObject(IntentMode.ACTION,explicit_command=True,requested_action='ghi file')
    p=ActionPlan('maintenance','file_write','run',fields={'path':str(f),'content':'new'},files=[str(f)])
    r=exe.prepare(i,p,{'current_turn_id':1},[])
    ck(r['would_authorize'] is True,'ACTION may authorize when valid')

# CONTINUE may authorize only with active task/context.
with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'a.txt'; f.write_text('old',encoding='utf-8')
    i=IntentObject(IntentMode.CONTINUE,explicit_command=True,requested_action='tiếp')
    p=ActionPlan('maintenance','file_write','run',fields={'path':str(f),'content':'new'},files=[str(f)])
    r=exe.prepare(i,p,{'current_turn_id':2,'active_task':{'task_id':'T1'}},[])
    ck(r['would_authorize'] is True,'CONTINUE may authorize with valid active task')

# CANCEL is not normal executor authorization.
i=IntentObject(IntentMode.CANCEL,explicit_command=True)
p=ActionPlan('maintenance','file_write','run',fields={'path':'x','content':'y'},files=['x'])
r=exe.prepare(i,p,{'current_turn_id':3,'active_task':{'task_id':'T1'}},[])
ck(r['would_authorize'] is False,'CANCEL blocked from normal execution path')

# 2) Cancel lifecycle stays separate from normal execution and targets exact execution.
runs=ExecutionManager(); p=ActionPlan('maintenance','file_write','run',fields={'path':'x','content':'y'},files=['x'])
eid=runs.create(p)
c=runs.cancel(eid)
ck((not c['ok']) and c['execution_id']==eid,'cancel targets exact execution')
ck(c['status']=='CANCEL_FAILED' and c['reason']=='cancel_not_supported','cancel without real callback is truthful')

# RUNNING execution also requires real tool cancel support.
p2=ActionPlan('maintenance','file_write','run',fields={'path':'x','content':'y'},files=['x']); eid2=runs.create(p2); runs.set(eid2,'RUNNING')
c2=runs.cancel(eid2)
ck((not c2['ok']) and c2['reason']=='cancel_not_supported','running execution cannot fake cancel')

# 3) Multi-turn structured resolution primitives, not intent-only.
with tempfile.TemporaryDirectory() as td:
    mem=ConversationContextManager(Path(td)/'m.json'); refs=ReferenceResolver()
    mem.update_session(current_target='maintenance',current_files=['app/modules/ga_brain/service.py'],last_identified_problems=['router sai intent'])
    ctx=mem.snapshot({})
    a=IntentObject(IntentMode.ACTION,context_references=['nó'])
    rr=refs.resolve(a,ctx)
    ck(rr['resolved'].get('nó')==['app/modules/ga_brain/service.py'],'pronoun resolves exact AI file')
    b=IntentObject(IntentMode.ACTION,context_references=['mấy lỗi đó'])
    rr2=refs.resolve(b,ctx)
    ck(rr2['resolved'].get('mấy lỗi đó')==['router sai intent'],'problems reference resolves exact problems')

# 4) Constraint lifecycle stays structurally correct under multi-turn task changes.
with tempfile.TemporaryDirectory() as td:
    mem=ConversationContextManager(Path(td)/'m.json')
    mem.add_constraint({'scope':'SESSION','effect':'FORBID','rule':'không đụng bot','target':'bot','source_turn':1})
    ck(any(x['target']=='bot' for x in mem.constraints(True)),'session constraint active')
    mem.revoke_constraints({'target':'bot'})
    ck(not mem.constraints(True),'session revoke removes active rule')
    mem.add_constraint({'scope':'SESSION','effect':'ALLOW','rule':'cho phép bot','target':'bot','source_turn':2})
    active=mem.constraints(True)
    ck(len(active)==1 and active[0]['effect']=='ALLOW','override leaves one active allow rule')

print(json.dumps({'suite':'v11.3_test_hardening','passed':PASSED,'failed':0,'skipped':0},ensure_ascii=False))
