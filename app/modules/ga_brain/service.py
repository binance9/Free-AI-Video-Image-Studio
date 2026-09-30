from __future__ import annotations
import json,re
from pathlib import Path
from .context_manager import ConversationContextManager
from .core_types import IntentMode,IntentObject,RunStatus
from .model_client import OllamaClient
from .intent_router import IntentRouter
from .planner import Planner
from .tool_registry import ToolRegistry
from .permission_gate import PermissionGate
from .requirement_validator import RequirementValidator
from .execution_manager import ExecutionManager
from .executor import ToolExecutor
from .verifier import ResultVerifier
from .response_engine import ResponseEngine
from .reference_resolver import ReferenceResolver
from .constraint_manager import ConstraintManager
from .model_router import ModelRouter

MODULES={'cut':'Cắt video','merge':'Ghép video','caption':'Phụ đề AI','bgremove':'Dọn video AI','aiimage':'AI Ảnh','music':'Thêm nhạc','sticker':'Emoji & Sticker','facebook':'Tải Facebook','taivideoweb':'Tải Video Web','text':'Văn bản','image':'Ảnh / Overlay','character2d':'Nhân vật 2D','ai3d':'Nhân vật 3D','dovat3d':'Đồ vật 3D','bandohd':'Bản đồ HD','gameready':'Game Ready (rig+animation)','maintenance':'Code / File'}

# Real bug found 2026-08-31: Planner (qwen3:8b) repeatedly picked target=ai3d
# (heavy Hunyuan3D/diffusers mesh pipeline, minutes + GB RAM) for a plain
# "tạo ảnh AI"/"tạo hình" request, apparently anchored on a PRIOR turn's
# active_task/pending_plan still being ai3d - confirmed reproducible even
# after strengthening tool_registry.py descriptions and PLANNER_SYSTEM
# instructions (prompt-only fix was not enough for this 8B model). Same
# "never trust the model alone for a safety/cost-relevant decision" pattern
# as BEAUTY_TRIGGER_WORDS/weapon-conflict check elsewhere in this file -
# deterministic keyword backstop that runs AFTER the Planner, not instead of it.
_3D_CUE_WORDS=re.compile(r'\b(3d|mo hinh|mô hình|model|mesh|khoi|khối|game)\b',re.I)
_FLAT_IMAGE_CUE_WORDS=re.compile(r'\b(anh|ảnh|hinh|hình|photo|picture|image)\b',re.I)
def _looks_like_flat_image_request(text:str)->bool:
    t=str(text or '')
    return bool(_FLAT_IMAGE_CUE_WORDS.search(t)) and not bool(_3D_CUE_WORDS.search(t))
CORE_VERSION='V12'

class NativeBrain:
    def __init__(self,root:Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.cfg_path=self.root/'config.json'
        defaults={'ollama_url':'http://127.0.0.1:11434','main_model':'qwen3:30b','fast_model':'qwen3:8b','chat_keep_alive':'90s','deep_keep_alive':0,'tool_execution_enabled':True}
        if self.cfg_path.is_file():
            try:
                o=json.loads(self.cfg_path.read_text(encoding='utf-8')); defaults.update(o if isinstance(o,dict) else {})
            except Exception: pass
        defaults['main_model']='qwen3:30b'; self.cfg=defaults; self.cfg_path.write_text(json.dumps(defaults,ensure_ascii=False,indent=2),encoding='utf-8')
        self.memory=ConversationContextManager(self.root/'memory.json'); self.models=OllamaClient(defaults['ollama_url'],main_model=defaults['main_model'],fast_model=defaults.get('fast_model','qwen3:8b'),chat_keep_alive=defaults.get('chat_keep_alive','90s'),deep_keep_alive=defaults.get('deep_keep_alive',0)); self.ollama=self.models
        self.model_router=ModelRouter()
        self.registry=ToolRegistry(); self.router=IntentRouter(self.models,self.model_router); self.planner=Planner(self.models,self.registry,self.model_router); self.gate=PermissionGate(); self.requirements=RequirementValidator(); self.executions=ExecutionManager(); self.executor=ToolExecutor(self.registry,self.gate,self.requirements,self.executions,enabled=bool(defaults.get('tool_execution_enabled'))); self.verifier=ResultVerifier(self.registry); self.responses=ResponseEngine(self.models,self.model_router); self.refs=ReferenceResolver(); self.constraints=ConstraintManager(self.models,self.memory,self.model_router)
    def _context(self,runtime=None): return self.memory.snapshot(runtime if isinstance(runtime,dict) else {})
    def route_stats(self): return self.model_router.stats()
    def route_log(self,limit=50): return self.model_router.recent(limit)
    def _truthful_action_reply(self,plan,ex):
        limitations=(ex.get('tool') or {}).get('limitations') or []
        limit_note=(' Giới hạn thật của tool này: '+' '.join(limitations)) if limitations else ''
        dropped=plan.fields.get('reference_dropped_reason')
        drop_note=f" LƯU Ý: {dropped}." if dropped else ''
        if ex.get('reason')=='core_only_phase_tools_locked' and ex.get('would_authorize'): return f"Tao hiểu ACTION, plan/tool đã qua gate và requirements (execution_id={ex.get('execution_id')}). V11.3 vẫn khóa side-effect nên CHƯA chạy tool thật.{drop_note}{limit_note}"
        if ex.get('reason')=='authorized': return f"Đã CẤP QUYỀN thật, tool đang được bấm chạy (execution_id={ex.get('execution_id')}). Theo dõi tiến độ ngay trong khung {MODULES.get(plan.target,plan.target)}; tao sẽ không báo XONG cho tới khi có bằng chứng thật.{drop_note}{limit_note}"
        if not ex.get('would_authorize'): return f"CHƯA thực thi. Gate chặn: {ex.get('reason')}."
        return f"Execution đã được cấp quyền; chưa được báo SUCCESS nếu verifier chưa có evidence.{limit_note}"
    def interact(self,message,context=None,image_path=None,image_name=None):
        runtime=context if isinstance(context,dict) else {}; msg=str(message or '').strip();
        if image_name: runtime.update({'attachment':True,'attachment_name':image_name})
        elif image_path: runtime['attachment']=True
        if not msg: msg='[Owner gửi một ảnh nhưng chưa kèm lệnh.]' if runtime.get('attachment') else ''
        turn=self.memory.add_turn('user',msg,image_name=runtime.get('attachment_name')); ctx=self._context(runtime)
        # Constraint changes are orthogonal to intent and can revoke old rules immediately.
        c_ops=self.constraints.parse(msg,ctx); c_changes=self.constraints.apply(c_ops,turn,ctx); ctx=self._context(runtime); ctx['current_turn_id']=turn
        intent=self.router.classify(msg,ctx)
        # Fail-safe persistence when the constraint parser is unavailable but the semantic router
        # has explicitly extracted owner constraints. Restrictive fallback is SESSION-scoped;
        # normal V11.3 path uses ConstraintManager structured scopes above.
        if not c_changes and (intent.constraints or intent.forbidden_actions):
            for rule in intent.constraints:
                self.memory.add_constraint({'scope':'SESSION','effect':'ALLOW','rule':str(rule),'source_turn':turn})
            for rule in intent.forbidden_actions:
                self.memory.add_constraint({'scope':'SESSION','effect':'FORBID','rule':str(rule),'source_turn':turn})
            ctx=self._context(runtime); ctx['current_turn_id']=turn
        # Entity capture is not intent routing: preserve explicit file/path mentions as structured
        # session state so later pronouns can resolve the actual object instead of a generic target.
        explicit_paths=[]
        for token in re.findall(r'(?:(?:[A-Za-z]:[\\/])|(?:\.?\.?[\\/]))?[^\s"<>|]+\.(?:py|js|json|md|txt|zip)',msg,re.I):
            clean=token.strip('.,;:()[]{}')
            if clean and clean not in explicit_paths: explicit_paths.append(clean)
        if explicit_paths:
            self.memory.update_session(current_files=explicit_paths)
            ctx=self._context(runtime); ctx['current_turn_id']=turn
        ref=self.refs.resolve(intent,ctx)
        # Keep structured session state current so later pronouns/references resolve to the
        # actual object from previous turns instead of relying only on raw chat history.
        session_updates={}
        if intent.target:
            session_updates['current_target']=intent.target
        resolved_values=list((ref.get('resolved') or {}).values())
        file_values=[]
        for value in resolved_values:
            if isinstance(value,str) and (value.endswith(('.py','.js','.json','.md','.txt','.zip')) or '/' in value or '\\' in value): file_values.append(value)
            elif isinstance(value,list):
                file_values.extend([x for x in value if isinstance(x,str) and (x.endswith(('.py','.js','.json','.md','.txt','.zip')) or '/' in x or '\\' in x)])
        if file_values:
            session_updates['current_files']=file_values
        if ref.get('resolved'):
            refs_map=dict(ctx.get('references_map') or {})
            refs_map.update(ref['resolved'])
            session_updates['references']=refs_map
        if session_updates:
            self.memory.update_session(**session_updates)
            ctx=self._context(runtime); ctx['current_turn_id']=turn
        if ref['unresolved'] and intent.owner_intent in {IntentMode.ACTION,IntentMode.CONTINUE}:
            intent.needs_clarification=True
        if intent.owner_intent==IntentMode.CANCEL:
            cancel=self.executions.cancel()
            if cancel.get('reason')=='no_active_execution':
                self.memory.clear_active_task(); reply='Không có execution đang chạy để hủy.'
            elif cancel.get('reason')=='cancel_not_supported': reply=f"Không thể giả vờ đã dừng: cancel_not_supported ({cancel.get('execution_id')})."
            else:
                self.memory.clear_active_task(); s=self.memory.session(); arr=s.setdefault('cancelled_tasks',[]); arr.append(cancel); self.memory.save(); reply=f"Đã hủy execution {cancel.get('execution_id')}."
            self.memory.add_turn('assistant',reply,meta={'intent':intent.to_dict(),'cancel':cancel,'resolution':ref}); return {'mode':'chat','message':reply,'intent':intent.to_dict(),'cancel':cancel,'brain_mode':CORE_VERSION,'constraint_changes':c_changes,'resolution':ref,'active_task':self.memory.active_task(),'active_constraints':self.memory.constraints(True,task_id=((self.memory.active_task() or {}).get('task_id')))}
        if intent.owner_intent==IntentMode.CONTINUE and (intent.needs_clarification or not ctx.get('active_task')):
            reply='TARGET_UNRESOLVED: chưa có nhiệm vụ đủ rõ để tiếp tục; tao không tự mặc định hay đoán target.'; self.memory.add_turn('assistant',reply,meta={'intent':intent.to_dict()}); return {'mode':'clarify','message':reply,'intent':intent.to_dict(),'brain_mode':CORE_VERSION}
        if intent.owner_intent in {IntentMode.CHAT,IntentMode.QUESTION,IntentMode.ANALYZE}:
            extra=None
            if image_path and intent.owner_intent==IntentMode.ANALYZE:
                vision=self.models.analyze_image(image_path,msg); extra={'vision':vision};
                if vision.get('summary'): self.memory.update_session(last_analysis=vision['summary'],image=image_name)
            reply=self.responses.answer(msg,intent,ctx,analysis_extra=extra)
            if intent.owner_intent==IntentMode.ANALYZE: self.memory.update_session(last_analysis=reply,last_identified_problems=[reply])
            self.memory.add_turn('assistant',reply,meta={'intent':intent.to_dict(),'resolution':ref}); return {'mode':'chat','message':reply,'intent':intent.to_dict(),'brain_mode':CORE_VERSION,'analysis':extra,'constraint_changes':c_changes,'resolution':ref,'active_constraints':self.memory.constraints(True,task_id=((self.memory.active_task() or {}).get('task_id')))}
        if intent.owner_intent in {IntentMode.ACTION,IntentMode.CONTINUE}:
            if intent.needs_clarification:
                reply='TARGET_UNRESOLVED: reference/target chưa đủ chắc; tao chưa lập execution.'; self.memory.add_turn('assistant',reply); return {'mode':'clarify','message':reply,'intent':intent.to_dict(),'brain_mode':CORE_VERSION}
            plan,err=self.planner.build(msg,intent,ctx)
            if plan is None:
                # V13 deterministic backstop: if the Planner LLM failed to pick
                # a tool but the owner's message clearly mentions 2D character
                # keywords, don't give up with no_matching_tool — directly
                # resolve to character_2d_generate.  This fixes the case
                # where the 8B model returns empty tool_name for a valid
                # "nhân vật 2D" request.
                if err == 'no_matching_tool':
                    _msg_lower = str(msg or '').lower()
                    _2d_char_cues = any(w in _msg_lower for w in (
                        'nhân vật 2d', 'nhan vat 2d', '2d character', 'character 2d',
                        '2d sprite', 'sprite 2d', 'nhân vật 2', 'nhan vat 2',
                    ))
                    _char_cues = any(w in _msg_lower for w in (
                        'nhân vật', 'nhan vat', 'warrior', 'archer', 'swordsman',
                        'kiếm sĩ', 'kiem si', 'cung thủ', 'cung thu', 'hero', 'heroine',
                        'character',
                    ))
                    _2d_cues = '2d' in _msg_lower or 'sprite' in _msg_lower
                    if _2d_char_cues or (_char_cues and _2d_cues):
                        tool = self.registry.get('character_2d_generate')
                        if tool:
                            from .core_types import ActionPlan
                            import uuid as _uuid
                            plan = ActionPlan(
                                target=tool.target, tool_name=tool.name,
                                action='run', fields={'prompt': str(msg)},
                                constraints=list(intent.constraints),
                                forbidden_actions=list(intent.forbidden_actions),
                                expected_result=str(intent.expected_result or ''),
                                needs_user='', reason='deterministic_backstop_2d_character',
                                confidence=0.90, files=[],
                                execution_id=_uuid.uuid4().hex,
                            )
                            err = None
                if plan is None:
                    reply='CHƯA thực thi: '+(err or 'no_matching_tool'); self.memory.add_turn('assistant',reply); return {'mode':'clarify','message':reply,'intent':intent.to_dict(),'brain_mode':CORE_VERSION}
            if ref['resolved']: plan.fields.setdefault('resolved_references',ref['resolved'])
            if plan.target=='ai3d' and _looks_like_flat_image_request(msg):
                flat_tool=self.registry.get('image_generate_edit')
                if flat_tool:
                    plan.target=flat_tool.target; plan.tool_name=flat_tool.name
                    # Once the Planner's target choice is proven wrong for this turn, its other
                    # fields (esp. 'prompt') are not trustworthy either - seen carrying over
                    # stale details (weapon, "3D") from the PREVIOUS turn's plan verbatim.
                    # Fall back to the owner's own raw text rather than the model's guess.
                    plan.fields['prompt']=msg
                    plan.fields.pop('color',None)
                    plan.reason=(plan.reason+' ' if plan.reason else '')+'(đã tự sửa: owner chỉ nói "ảnh", không nhắc 3D - chuyển sang tool ảnh 2D nhẹ thay vì dựng mesh 3D nặng, và dùng thẳng câu chữ gốc thay vì mô tả model tự bịa.)'
            if image_path and runtime.get('attachment'):
                # Neutral, request-text-free description on purpose - a version that embeds
                # the owner's own request ("tạo nhân vật cầm đao") was confirmed by direct
                # testing to make the vision model hallucinate the image already matches the
                # request instead of reporting what is really in it, defeating the weapon-
                # conflict check below silently.
                vision=self.models.describe_character_image(image_path)
                if vision.get('summary'): plan.fields.setdefault('vision_reference',vision['summary'])
                # Real bug found 2026-08-30: character_3d_generate/character_2d_generate
                # build 3D/2D output DIRECTLY from an attached reference image's real
                # shape - text can restyle/recolor but cannot invent a weapon the photo
                # doesn't show (a text-only Planner has no way to know what's actually
                # IN the photo to catch this itself - a longer prompt instruction alone
                # did not fix it, confirmed by direct testing). Deterministic check using
                # the same weapon dictionaries nhan_vat_2d already uses: if vision's own
                # description of the photo names a different weapon than this turn's
                # prompt, the stale photo no longer matches what owner is asking for -
                # drop it so generation falls back to text-only (fresh concept) instead
                # of silently reproducing the old photo's weapon.
                if plan.target in {'ai3d','character2d'}:
                    from app.modules.nhan_vat_2d.spec_parser import parse_character_spec
                    photo_weapon=parse_character_spec(str(vision.get('summary') or '')).weapon_type
                    text_weapon=parse_character_spec(str(plan.fields.get('prompt') or msg)).weapon_type
                    if photo_weapon and text_weapon and photo_weapon!=text_weapon:
                        plan.files=[]
                        plan.fields['reference_dropped_reason']=f'ảnh cũ cho thấy {photo_weapon}, owner giờ muốn {text_weapon} - bỏ ảnh cũ, dùng mô tả chữ để vẽ concept mới'
            active=(ctx.get('active_task') or {}); task_id=active.get('task_id') or active.get('execution_id')
            scoped_constraints=self.memory.constraints(True,turn_id=turn,task_id=task_id)
            ex=self.executor.prepare(intent,plan,ctx,scoped_constraints)
            # ACTION-scoped constraints are one-shot and cannot become zombies.
            self.memory.consume_action_constraints(turn)
            if ex.get('core_gate_passed'):
                task={'execution_id':plan.execution_id,'task_id':task_id or plan.execution_id,'message':msg,'target':plan.target,'tool_name':plan.tool_name,'expected_result':plan.expected_result,'status':'PLANNED'}; self.memory.set_active_task(task); self.memory.update_session(pending_plan=plan.to_dict())
            reply=self._truthful_action_reply(plan,ex); self.memory.add_turn('assistant',reply,meta={'intent':intent.to_dict(),'plan':plan.to_dict(),'execution':ex,'resolution':ref}); return {'mode':'action' if ex.get('would_authorize') else 'clarify','message':reply,'intent':intent.to_dict(),'plan':plan.to_dict(),'execution':ex,'brain_mode':CORE_VERSION,'constraint_changes':c_changes,'resolution':ref,'resolved_target':plan.target,'active_constraints':self.memory.constraints(True,task_id=((self.memory.active_task() or {}).get('task_id')))}
        reply='Tao chưa xác định được intent; chưa có side effect.'; self.memory.add_turn('assistant',reply); return {'mode':'clarify','message':reply,'brain_mode':CORE_VERSION}
    def plan(self,message,context=None,force_target=None,optimize_only=False):
        ctx=self._context(context); intent=IntentObject(IntentMode.ACTION,target=force_target,requested_action=str(message),explicit_command=True,expected_result=str(message),confidence=1.0); p,e=self.planner.build(str(message),intent,ctx)
        if p is None: raise ValueError(e or 'Không lập được kế hoạch')
        if force_target and force_target in MODULES:
            t=self.registry.by_target(force_target)
            if t: p.target=force_target; p.tool_name=t.name
        return p.to_dict()
    def record_tool_result(self,report):
        report=report if isinstance(report,dict) else {}; eid=str(report.get('execution_id') or ''); run=self.executions.get(eid) if eid else self.executions.active(); tool=(run or {}).get('plan',{}).get('tool_name') if run else report.get('tool_name'); vr=self.verifier.verify_report(report,tool,run=run); self.memory.update_session(last_result=vr.to_dict());
        if eid: self.executions.set(eid,vr.status.value,verification=vr.to_dict())
        if vr.status in {RunStatus.SUCCESS,RunStatus.FAILED,RunStatus.PARTIAL,RunStatus.CANCELLED}: self.memory.clear_active_task()
        return vr.to_dict()
