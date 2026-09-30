from __future__ import annotations
from .requirement_validator import RequirementValidator
from .execution_manager import ExecutionManager
class ToolExecutor:
    # Targets with a real native-run dispatcher in web/core/ga_brain.js (apply()+nativeRun()).
    # 'maintenance' (code_edit/file_write/...) has no such dispatcher and stays locked
    # regardless of `enabled` - there is nothing that would actually perform the write.
    WIRED_TARGETS={'aiimage','character2d','ai3d','dovat3d','bandohd','gameready'}
    def __init__(self,registry,gate,requirements=None,executions=None,enabled=False):
        self.registry=registry; self.gate=gate; self.requirements=requirements or RequirementValidator(); self.executions=executions or ExecutionManager(); self.enabled=bool(enabled)
    def prepare(self,intent,plan,context,active_constraints=None):
        if not plan.execution_id:self.executions.create(plan)
        elif not self.executions.get(plan.execution_id):self.executions.create(plan)
        base={'execution_id':plan.execution_id}
        ok,reason=self.gate.authorize(intent,plan,context)
        if not ok:return {**base,'authorized':False,'would_authorize':False,'reason':reason,'core_gate_passed':False}
        tool=self.registry.get(plan.tool_name)
        if tool is None:return {**base,'authorized':False,'would_authorize':False,'reason':'tool_not_registered','core_gate_passed':False}
        ok,reason=self.gate.capability_allow(tool,intent,plan)
        if not ok:return {**base,'authorized':False,'would_authorize':False,'reason':reason,'core_gate_passed':False}
        ok,reason=self.gate.constraints_allow(plan,intent,active_constraints,context)
        if not ok:return {**base,'authorized':False,'would_authorize':False,'reason':reason,'core_gate_passed':False}
        ok,reason=self.requirements.validate(tool,plan,context)
        if not ok:return {**base,'authorized':False,'would_authorize':False,'reason':reason,'core_gate_passed':False}
        if not self.enabled or plan.target not in self.WIRED_TARGETS:
            self.executions.set(plan.execution_id,'PLANNED',would_authorize=True)
            return {**base,'authorized':False,'would_authorize':True,'core_gate_passed':True,'reason':'core_only_phase_tools_locked','tool':tool.public_dict(),'plan':plan.to_dict()}
        self.executions.set(plan.execution_id,'RUNNING')
        return {**base,'authorized':True,'would_authorize':True,'core_gate_passed':True,'reason':'authorized','tool':tool.public_dict(),'plan':plan.to_dict()}
