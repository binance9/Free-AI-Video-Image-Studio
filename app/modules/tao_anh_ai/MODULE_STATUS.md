MODULE:
tao_anh_ai

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/tao_anh_ai/api_tao_anh_ai.py

FRONTEND_ENTRY:
web/modules/tao_anh_ai/tao_anh_ai.js

SMOKE_TEST:
pytest -q tests/smoke/test_tao_anh_ai_smoke.py

HEAVY_MODELS:
Diffusers (Stable Diffusion local, mặc định stable-diffusion-v1-5)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Constructor LocalImageService không load pipeline ngay (lazy) — smoke test không chạm model thật.
Phụ thuộc app.modules.chinh_sua_video.workspace.VideoWorkspace để import ảnh AI vào session.
