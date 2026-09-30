from __future__ import annotations

import json

from .core_types import IntentMode
from .model_router import ModelRouter, compact_context


RESPONSE_SYSTEM = """
Mày là Response Engine của Gà AI. Trả lời tiếng Việt tự nhiên, ngắn gọn, đúng câu owner hỏi.
Không bịa trạng thái. Nếu chưa chạy tool thì không được nói "đang chạy", "đã tạo", "đã sửa", "xong".
CHAT chỉ nói chuyện. QUESTION chỉ trả lời. ANALYZE chỉ phân tích. Nếu thiếu dữ liệu thì nói đúng dữ liệu thiếu.
Không lặp template kiểu "boss cứ yên tâm".
"""


class ResponseEngine:
    def __init__(self, model, router: ModelRouter | None = None):
        self.model = model
        self.router = router or ModelRouter()

    def answer(self, message, intent, context, analysis_extra=None):
        decision = self.router.route_response(intent.owner_intent.value if hasattr(intent.owner_intent, "value") else str(intent.owner_intent), message, context)
        ctx_for_prompt = context if not decision.fast else compact_context(context)
        packet = {
            "owner_message": message,
            "intent": intent.to_dict(),
            "context": ctx_for_prompt,
            "analysis_extra": analysis_extra,
        }
        try:
            text, _entry = self.router.call_chat(self.model, decision, [
                {"role": "system", "content": RESPONSE_SYSTEM},
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
            ])
            return text
        except Exception:
            if intent.owner_intent == IntentMode.QUESTION:
                return "Tao đang thiếu model AI để trả lời câu này chính xác; tao chưa thực hiện hành động nào."
            if intent.owner_intent == IntentMode.ANALYZE:
                return "Tao chưa phân tích được vì model AI chưa sẵn sàng; tao chưa sửa gì cả."
            return "Ừ, tao đang nghe. Tao chưa thực hiện hành động nào."
