MODULE:
phu_de

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/phu_de/api_phu_de.py

FRONTEND_ENTRY:
web/modules/phu_de/phu_de.js

SMOKE_TEST:
pytest -q tests/smoke/test_phu_de_smoke.py

HEAVY_MODELS:
faster-whisper (mặc định "small"), Argos Translate (gói ngôn ngữ tải riêng)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
translate_local cũ đã gộp vào module này thành dich_thuat.py (chỉ dùng cho dịch phụ đề).
Constructor LocalCaptionService không load model ngay (lazy) — smoke test không chạm Whisper thật.
