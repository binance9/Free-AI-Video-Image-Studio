from __future__ import annotations
import json,uuid
from .core_types import ActionPlan,IntentMode
from .model_router import ModelRouter,compact_context

PLANNER_SYSTEM='''Mày là Planner của Gà AI Core. Chỉ lập kế hoạch sau ACTION/CONTINUE.
Tool registry là nguồn sự thật capability. Không bịa file/ảnh/chức năng.
TUYỆT ĐỐI không tự xác nhận trạng thái vật lý/hệ thống. Không được đặt hoặc suy ra các field như backup_confirmed, file_exists, target_exists, write_confirmed, syntax_pass, test_pass, artifact_exists, output_exists. Những trạng thái đó chỉ do executor/verifier thực tế tạo.
Chọn tool_name/target dựa trên NỘI DUNG owner_message của LƯỢT NÀY, không dựa vào context.active_task/context.current_target của lượt TRƯỚC - context đó chỉ để tham chiếu (resolve "nó"/"ảnh trên"...), không phải để mặc định giữ nguyên domain cũ. Owner đổi từ "ảnh AI"/"ảnh 2D" sang "3D" (hoặc ngược lại) giữa các lượt là bình thường - ưu tiên đúng domain owner vừa nói, đừng dính vào target cũ vì "đang làm dở". aiimage/character2d là ẢNH PHẲNG (nhẹ, nhanh); ai3d là MESH 3D THẬT (nặng, chậm) - chỉ chọn ai3d khi owner nói rõ "3D"/"mô hình"/"model"/"mesh"/"game" ở lượt này.
Nếu thiếu dữ liệu thì action="prepare" và needs_user nói rõ.
Trả JSON {"tool_name":"","target":"","action":"run|prepare","fields":{},"files":[],"constraints":[],"forbidden_actions":[],"expected_result":"","needs_user":"","reason":"","confidence":0.0}'''
PHYSICAL_ASSERTIONS={'backup_confirmed','file_exists','target_exists','write_confirmed','syntax_pass','test_pass','tests_pass','artifact_exists','output_exists','path_exists','backup_exists'}
class Planner:
    def __init__(self,model,registry,router:ModelRouter|None=None): self.model=model; self.registry=registry; self.router=router or ModelRouter()
    def _sanitize_fields(self,fields):
        fields=dict(fields or {})
        for k in list(fields):
            if str(k).lower() in PHYSICAL_ASSERTIONS: fields.pop(k,None)
        return fields
    def _call(self,original,intent,context,decision):
        ctx_for_prompt=context if not decision.fast else compact_context(context)
        packet={'owner_message':original,'intent':intent.to_dict(),'context':ctx_for_prompt,'tools':self.registry.public_list()}
        return self.router.call_json(self.model,decision,[{'role':'system','content':PLANNER_SYSTEM},{'role':'user','content':json.dumps(packet,ensure_ascii=False)}])
    def build(self,message,intent,context):
        active=context.get('active_task') or {}; original=str(active.get('message') or message) if intent.owner_intent==IntentMode.CONTINUE else str(message)
        decision=self.router.route_planner(original,context,intent)
        try:
            obj,_entry=self._call(original,intent,context,decision)
        except Exception as exc:return None,f'planner_unavailable:{type(exc).__name__}:{exc}'
        # V12 requirement #7: escalate a low-confidence or failed fast plan to
        # the deep model + full context before giving up - a wrong tool/target
        # pick is exactly the kind of mistake action_precision gates catch.
        escalation=self.router.escalate_planner(decision,obj.get('confidence'),has_error=not bool(obj.get('tool_name') or obj.get('target')))
        if escalation is not None:
            try: obj,_entry=self._call(original,intent,context,escalation)
            except Exception as exc:return None,f'planner_unavailable:{type(exc).__name__}:{exc}'
        tool=self.registry.get(obj.get('tool_name')) or (self.registry.by_target(obj.get('target')) if obj.get('target') else None)
        if tool is None:return None,'no_matching_tool'
        plan=ActionPlan(target=tool.target,tool_name=tool.name,action='run' if str(obj.get('action') or 'prepare')=='run' else 'prepare',fields=self._sanitize_fields(obj.get('fields')),constraints=list(intent.constraints)+[str(x) for x in obj.get('constraints',[])],forbidden_actions=list(intent.forbidden_actions)+[str(x) for x in obj.get('forbidden_actions',[])],expected_result=str(obj.get('expected_result') or intent.expected_result or ''),needs_user=str(obj.get('needs_user') or ''),reason=str(obj.get('reason') or ''),confidence=float(obj.get('confidence') or 0.0),files=[str(x) for x in obj.get('files',[]) if str(x).strip()],execution_id=uuid.uuid4().hex)
        return plan,None
