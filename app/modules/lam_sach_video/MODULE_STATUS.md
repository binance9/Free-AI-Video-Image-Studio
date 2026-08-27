MODULE:
lam_sach_video

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/lam_sach_video/api_lam_sach_video.py

FRONTEND_ENTRY:
web/modules/lam_sach_video/lam_sach_video.js

SMOKE_TEST:
pytest -q tests/smoke/test_lam_sach_video_smoke.py

HEAVY_MODELS:
rembg (u2net_human_seg / isnet-general-use), OpenCV inpaint

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Runtime cài riêng qua SETUP_VIDEO_CLEANUP_AI.bat, không dùng chung venv với Character HD.
Smoke test có regression check cho bug đường dẫn subprocess (runtime.py) đã sửa ở phiên trước.
