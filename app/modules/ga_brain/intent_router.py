from __future__ import annotations

import json

from .core_types import IntentMode, IntentObject
from .model_router import ModelRouter, compact_context


INTENT_SYSTEM = """
Mày là Intent Router của Gà AI Core. Không thực thi công cụ.
Đọc message + conversation context rồi phân loại dựa trên Ý NGHĨA, không dựa vào từ khóa đơn lẻ.

Chỉ chọn đúng một mode:
CHAT = chỉ nói chuyện/nhận xét/tâm sự/báo trước một việc có thể làm sau.
QUESTION = đang hỏi thông tin/khả năng/trạng thái; tuyệt đối không coi câu hỏi là lệnh.
ANALYZE = yêu cầu xem/đánh giá/phân tích nhưng chưa cho phép thay đổi.
ACTION = owner đang ra lệnh thực hiện NGAY một thay đổi/tác vụ.
CONTINUE = owner ra lệnh tiếp tục đúng nhiệm vụ đang làm hoặc kế hoạch đã xác định trong context.
CANCEL = owner yêu cầu dừng/hủy hành động.

Cực quan trọng:
- "mày biết sửa code không?" = QUESTION.
- "ok, giờ tao sẽ gửi lệnh rồi mày vào làm nhé" = CHAT, vì đây là báo trước chứ chưa phải lệnh làm đối tượng cụ thể.
- "sẵn sàng tạo ảnh chưa?" = QUESTION.
- "ảnh này mà sáng hơn chắc đẹp" = CHAT.
- "làm ảnh này sáng hơn" = ACTION.
- "thôi chưa sửa, phân tích trước" = ANALYZE và phải chặn sửa.
- "giờ làm đi" chỉ là CONTINUE nếu context có active_task/kế hoạch rõ; nếu không thì needs_clarification=true.
- Không được tự invent target, file, ảnh hoặc nhiệm vụ.

Owner hay nói câu rất ngắn, không có tân ngữ cụ thể - đừng mặc định coi ngắn là CHAT:
- Một câu ngắn hỏi trạng thái/tiến độ/khả năng dù KHÔNG có dấu "?" vẫn là QUESTION, không phải CHAT: "sẵn sàng chưa", "xong chưa", "đang chạy gì đấy", "có hiểu tao nói ko", "3d khác 2d sao" đều là QUESTION.
- Động từ ra lệnh xem/soi/tìm/kiểm tra/đánh giá dù không có tân ngữ rõ vẫn là ANALYZE, không phải CHAT hay QUESTION: "soi giúp tao", "tìm nguyên nhân", "kiểm tra giúp" đều là ANALYZE.
- Chỉ coi là CHAT khi câu thật sự không yêu cầu owner đang chờ thông tin/đánh giá gì cả (than thở, bông đùa, nhận xét chung chung).

context_references CHỈ điền khi message dùng đại từ/chỉ định ("nó", "cái đó", "cái này", "thế", "mấy lỗi đó"...) trỏ về một thứ ĐÃ nhắc TRƯỚC ĐÓ trong hội thoại. Nếu message tự mô tả đầy đủ nội dung/đối tượng MỚI (ví dụ "tạo ảnh con mèo", "vẽ nhân vật nữ cầm kiếm", "làm video về biển") thì đó không phải tham chiếu - context_references PHẢI để trống []. Đừng suy diễn tham chiếu không cần thiết chỉ vì câu có danh từ.
context_references PHẢI là đúng cụm từ owner dùng (ví dụ "nó", "trong ảnh", "cái đó") - KHÔNG được chép tên trường JSON trong context (như "current_image", "current_target") vào đây, đó là dữ liệu nội bộ chứ không phải lời owner nói.

Trả JSON đúng schema:
{
 "owner_intent":"CHAT|QUESTION|ANALYZE|ACTION|CONTINUE|CANCEL",
 "conversation_mode":"short label",
 "target":null,
 "requested_action":null,
 "constraints":[],
 "context_references":[],
 "tools_required":[],
 "forbidden_actions":[],
 "expected_result":"",
 "confidence":0.0,
 "reason":"",
 "explicit_command":false,
 "prospective_only":false,
 "needs_clarification":false
}
"""


class IntentRouter:
    def __init__(self, model, router: ModelRouter | None = None):
        self.model = model
        self.router = router or ModelRouter()

    def _call(self, message: str, context: dict, decision):
        ctx_for_prompt = context if not decision.fast else compact_context(context)
        packet = {"owner_message": str(message), "context": ctx_for_prompt}
        return self.router.call_json(self.model, decision, [
            {"role": "system", "content": INTENT_SYSTEM},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
        ])

    def classify(self, message: str, context: dict) -> IntentObject:
        try:
            decision = self.router.route_intent(message, context)
            obj, _entry = self._call(message, context, decision)
            # V12 requirement #7: escalate FAST->DEEP on low confidence or a
            # borderline ACTION call using the model's OWN confidence field,
            # then re-classify with the deep model + full context. Never
            # silently trust a low-confidence fast read for a safety-relevant
            # mode.
            escalation = self.router.escalate_intent(decision, float(obj.get("confidence") or 0.0), str(obj.get("owner_intent") or "").upper())
            if escalation is not None:
                obj, _entry = self._call(message, context, escalation)
            mode = IntentMode(str(obj.get("owner_intent") or "CHAT").upper())
            intent = IntentObject(
                owner_intent=mode,
                conversation_mode=str(obj.get("conversation_mode") or mode.value),
                target=(str(obj.get("target")) if obj.get("target") else None),
                requested_action=(str(obj.get("requested_action")) if obj.get("requested_action") else None),
                constraints=[str(x) for x in obj.get("constraints", []) if str(x).strip()],
                context_references=[str(x) for x in obj.get("context_references", []) if str(x).strip()],
                tools_required=[str(x) for x in obj.get("tools_required", []) if str(x).strip()],
                forbidden_actions=[str(x) for x in obj.get("forbidden_actions", []) if str(x).strip()],
                expected_result=str(obj.get("expected_result") or ""),
                confidence=float(obj.get("confidence") or 0.0),
                reason=str(obj.get("reason") or ""),
                explicit_command=bool(obj.get("explicit_command")),
                prospective_only=bool(obj.get("prospective_only")),
                needs_clarification=bool(obj.get("needs_clarification")),
            )
        except Exception as exc:
            # Fail closed: if the AI router is unavailable, never guess an external action.
            return IntentObject(
                owner_intent=IntentMode.CHAT,
                conversation_mode="SAFE_FALLBACK",
                confidence=0.0,
                reason=f"Intent model unavailable: {type(exc).__name__}: {exc}",
                needs_clarification=True,
            )

        # Permission-oriented semantic validation. This is not a keyword classifier.
        if intent.owner_intent == IntentMode.ACTION and (not intent.explicit_command or intent.prospective_only):
            intent.owner_intent = IntentMode.CHAT
            intent.reason = "Blocked false action: action was not an explicit present command."
        if intent.owner_intent == IntentMode.CONTINUE and not context.get("active_task"):
            intent.needs_clarification = True
        return intent
