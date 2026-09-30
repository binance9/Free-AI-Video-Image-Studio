from __future__ import annotations
from .core_types import IntentMode
class PermissionGate:
    SIDE_EFFECT_MODES={IntentMode.ACTION,IntentMode.CONTINUE}
    def authorize(self,intent,plan=None,context=None):
        context=context or {}
        if intent.owner_intent not in self.SIDE_EFFECT_MODES:return False,'intent_not_action'
        if intent.owner_intent==IntentMode.ACTION and not intent.explicit_command:return False,'no_explicit_command'
        if intent.prospective_only:return False,'prospective_statement_only'
        if intent.owner_intent==IntentMode.CONTINUE and not context.get('active_task'):return False,'no_active_task_to_continue'
        if plan is None:return False,'missing_plan'
        if not plan.target or not plan.tool_name:return False,'unresolved_target'
        return True,'authorized'
    def _scope_applies(self,r,context):
        scope=str(r.get('scope') or 'SESSION').upper()
        if scope=='SESSION':return True
        if scope=='ACTION':
            current=context.get('current_turn_id')
            return current is not None and int(r.get('action_turn') or -1)==int(current)
        if scope=='TASK':
            active=context.get('active_task') or {}; tid=active.get('task_id') or active.get('execution_id')
            rid=r.get('task_id')
            return (not rid) or (tid is not None and rid==tid)
        return False
    def constraints_allow(self,plan,intent,active_constraints=None,context=None):
        context=context or {}; rules=list(active_constraints or [])
        for x in getattr(intent,'forbidden_actions',[]) or []:rules.append({'status':'ACTIVE','effect':'FORBID','rule':str(x),'scope':'ACTION','action_turn':context.get('current_turn_id')})
        target=str(plan.target or '').lower(); tool=str(plan.tool_name or '').lower(); files=[str(x).lower() for x in getattr(plan,'files',[]) or []]
        for r in rules:
            if r.get('status','ACTIVE')!='ACTIVE' or str(r.get('effect','')).upper()!='FORBID' or not self._scope_applies(r,context):continue
            rt=str(r.get('target') or '').lower(); rr=str(r.get('rule') or '').lower(); rtool=str(r.get('tool') or '').lower(); rf=str(r.get('file_scope') or '').lower(); violation=False
            if rt and (rt==target or rt in target):violation=True
            if rtool and rtool==tool:violation=True
            if rf and any(rf in f for f in files):violation=True
            if not any((rt,rtool,rf)):
                if 'bot' in rr and ('bot' in target or 'bot' in tool or any('bot' in f for f in files)):violation=True
                if 'ai' in rr and ('không' in rr or 'cấm' in rr or 'khong' in rr or 'cam' in rr) and ('ai' in target or any('ga_brain' in f for f in files)):violation=True
            if violation:return False,'constraint_violation'
        return True,'ok'
    def capability_allow(self,tool,intent,plan):
        if intent.owner_intent.value not in tool.supported_intents:return False,'tool_intent_mismatch'
        if tool.target!=plan.target:return False,'tool_target_mismatch'
        return True,'ok'
