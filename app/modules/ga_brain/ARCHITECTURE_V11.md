# GÀ AI CORE V11 — CORE-FIRST ARCHITECTURE

## Audit nguồn cũ

1. `service.py` là monolith hơn 1000 dòng, trộn memory, Ollama, intent, planner, tool-specific routing và policy.
2. Intent có nhiều fast-path/keyword target, khiến câu nói về công việc dễ bị hiểu thành ACTION.
3. `ga_owner.js` chứa một fallback brain riêng, tạo ra hai bộ não có thể route khác nhau.
4. `ga_brain.js` từng có lớp force-action bằng regex/keyword ở frontend.
5. `active_goal/pending_action` cũ có thể giữ target đoán sai và làm CONTINUE nhảy nhầm module.
6. Trạng thái plan/executing/success chưa được tách cứng ở AI Core.
7. Main model cũ là `qwen3:8b`.

## Kiến trúc V11

OWNER MESSAGE
→ Context Manager
→ Intent Router (model-first)
→ Permission Gate
→ Planner
→ Tool Registry
→ Tool Executor directive
→ Result Verifier
→ Response Engine

Module mới:
- `core_types.py`
- `context_manager.py`
- `model_client.py`
- `intent_router.py`
- `planner.py`
- `tool_registry.py`
- `permission_gate.py`
- `executor.py`
- `verifier.py`
- `response_engine.py`
- `service.py` chỉ còn orchestration.

## Luật side-effect

V11 đang ở **CORE QUALIFICATION MODE**: `tool_execution_enabled=false`.

- CHAT / QUESTION / ANALYZE: side-effect bị khóa cứng.
- ACTION: Router phải xác nhận `explicit_command=true` và không phải câu báo trước.
- CONTINUE: bắt buộc phải có `active_task` thật trong context.
- Planner có thể chọn tool/capability, nhưng Tool Executor chưa cho chạy tool native ở phase này.
- Chỉ sau khi AI Core được owner test đạt mới bật phase kết nối tool.

## Model

- Main brain: `qwen3:30b`
- Fast fallback: `qwen3:8b`
- Vision: model vision riêng nếu có; không có thì không giả vờ nhìn ảnh.

## Ảnh trong chat

`ga_owner.js` chỉ còn UI/voice/attachment transport, không còn fallback brain.
Ảnh đang chọn = draft. Khi bấm gửi, ảnh được đưa vào message bubble trong lịch sử chat; composer sạch nhưng file gần nhất vẫn giữ làm context cho lượt tiếp theo.
