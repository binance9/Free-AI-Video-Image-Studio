import json
from app.modules.ga_brain.intent_router import IntentRouter

class ScenarioModel:
    def json(self,msgs,**kw):
        text=json.loads(msgs[-1]['content'])['owner_message'].lower()
        # deterministic pipeline regression only; NOT real-model evidence
        mapping={
          'ê gà':'CHAT','mày biết tạo ảnh 3d không?':'QUESTION','tạo cho tao ảnh 3d cây kiếm':'ACTION',
          'xem code này lỗi đâu':'ANALYZE','sửa mấy lỗi đó đi':'ACTION','chỉ sửa ai, không đụng bot':'CHAT',
          'hôm nay tao mệt':'CHAT','ảnh này mà sáng hơn chắc đẹp':'CHAT','làm ảnh này sáng hơn':'ACTION',
          'thôi chưa sửa, phân tích trước':'ANALYZE','sẵn sàng tạo ảnh chưa':'QUESTION','tao sẽ gửi lệnh rồi mày vào tạo nhé':'CHAT',
          'dừng':'CANCEL','làm tiếp':'CONTINUE','mày có biết sửa code khi bot bị lỗi ko':'QUESTION','phân tích trước':'ANALYZE','xóa cái này':'ACTION'}
        mode=mapping[text]
        return {'owner_intent':mode,'conversation_mode':mode,'target':'maintenance' if mode=='ACTION' else None,'requested_action':text if mode=='ACTION' else None,'constraints':[],'context_references':[],'tools_required':[],'forbidden_actions':[],'expected_result':'','confidence':1.0,'reason':'scenario','explicit_command':mode=='ACTION','prospective_only':False,'needs_clarification':False}

cases=[
('ê gà','CHAT',{}),('mày biết tạo ảnh 3d không?','QUESTION',{}),('tạo cho tao ảnh 3d cây kiếm','ACTION',{}),('xem code này lỗi đâu','ANALYZE',{}),('sửa mấy lỗi đó đi','ACTION',{}),('chỉ sửa ai, không đụng bot','CHAT',{}),('hôm nay tao mệt','CHAT',{}),('ảnh này mà sáng hơn chắc đẹp','CHAT',{}),('làm ảnh này sáng hơn','ACTION',{}),('thôi chưa sửa, phân tích trước','ANALYZE',{}),('sẵn sàng tạo ảnh chưa','QUESTION',{}),('tao sẽ gửi lệnh rồi mày vào tạo nhé','CHAT',{}),('dừng','CANCEL',{}),('làm tiếp','CONTINUE',{'active_task':{'target':'maintenance'}}),('mày có biết sửa code khi bot bị lỗi ko','QUESTION',{}),('phân tích trước','ANALYZE',{}),('xóa cái này','ACTION',{})]
r=IntentRouter(ScenarioModel()); passed=0
for text,exp,ctx in cases:
 got=r.classify(text,ctx).owner_intent.value
 assert got==exp,(text,got,exp); passed+=1
print(json.dumps({'suite':'regression_17_scenario_pipeline','passed':passed,'failed':0,'note':'ScenarioModel unit/regression only; not real-model evidence'},ensure_ascii=False))
