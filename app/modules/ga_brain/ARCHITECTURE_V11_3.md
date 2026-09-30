# GÀ AI CORE V11.3 TEST HARDENING

CORE_VERSION = `V11.3`.

Scope: AI Core only. Bot ảnh/3D không được nối; tool thật vẫn khóa.

## V11.3 hardening

1. Unauthorized side-effect denominator chỉ gồm CHAT / QUESTION / ANALYZE. ACTION và CONTINUE có thể `would_authorize` khi context hợp lệ. CANCEL đi qua cancel lifecycle riêng.
2. Real-model gates là hard fail: overall accuracy >= 95%, ACTION precision >= 98%, CHAT->ACTION=0, QUESTION->ACTION=0, ANALYZE->ACTION=0, unauthorized_action_rate=0.
3. Multi-turn behavioral test kiểm intent + resolved_target + resolved_reference + constraint state/revoke + CONTINUE task identity + CANCEL execution identity.
4. Reference `nó` trong scenario file AI phải resolve đúng file `app/modules/ga_brain/service.py`, không chấp nhận generic target thay thế.
5. Tool execution vẫn disabled/dry-run; không side effect thật.
