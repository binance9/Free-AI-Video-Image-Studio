from __future__ import annotations
import json
from .model_router import ModelRouter,compact_context
CONSTRAINT_SYSTEM='''Mày là Constraint Parser. Không hành động. Đọc câu owner và state constraint hiện tại.
Trả JSON {"operations":[...]} với operation ADD|REPLACE|REVOKE|CLEAR.
ADD/REPLACE có scope SESSION|TASK|ACTION, effect ALLOW|FORBID, rule, target(optional), tool(optional), file_scope(optional).
ACTION chỉ áp dụng hành động ở chính lượt này. TASK áp dụng task đang nói tới và hết khi task kết thúc/hủy. SESSION mới sống toàn phiên.
Nếu owner đổi ý như "giờ cho phép sửa bot" hoặc "bỏ giới hạn đó" phải REVOKE/SUPERSEDE rule cũ. Không để zombie constraint.
Nếu câu không thay đổi constraint, operations=[] . Không bịa scope/target.'''
class ConstraintManager:
    def __init__(self,model,memory,router:ModelRouter|None=None): self.model=model; self.memory=memory; self.router=router or ModelRouter()
    def parse(self,message,context):
        try:
            decision=self.router.route_constraint(message,context)
            obj,_entry=self.router.call_json(self.model,decision,[{'role':'system','content':CONSTRAINT_SYSTEM},{'role':'user','content':json.dumps({'message':message,'active_constraints':context.get('active_constraints',[]),'active_task':context.get('active_task')},ensure_ascii=False)}])
            return list(obj.get('operations') or [])
        except Exception:return []
    def apply(self,ops,source_turn=0,context=None):
        context=context or {}; changes=[]; active=context.get('active_task') or {}; active_task_id=active.get('task_id') or active.get('execution_id')
        for op in ops:
            typ=str(op.get('operation') or '').upper(); scope=str(op.get('scope') or 'SESSION').upper()
            if typ=='CLEAR': changes.append({'operation':'CLEAR','count':self.memory.clear_constraints()}); continue
            matcher={k:op.get(k) for k in ('scope','target','tool','file_scope') if op.get(k) is not None}
            if typ=='REVOKE': changes.append({'operation':'REVOKE','count':self.memory.revoke_constraints(matcher)}); continue
            if typ=='REPLACE': self.memory.revoke_constraints(matcher)
            if typ in {'ADD','REPLACE'}:
                rule=dict(op); rule['source_turn']=source_turn
                if scope=='ACTION': rule['action_turn']=source_turn
                elif scope=='TASK': rule['task_id']=active_task_id
                changes.append({'operation':typ,'rule':self.memory.add_constraint(rule)})
        return changes
