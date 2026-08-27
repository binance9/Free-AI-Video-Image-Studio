MODULE:
tai_video

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/tai_video/api_tai_video.py

FRONTEND_ENTRY:
web/modules/tai_video/tai_video.js

SMOKE_TEST:
pytest -q tests/smoke/test_tai_video_smoke.py

HEAVY_MODELS:
Không có (dùng thư viện yt-dlp)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Chỉ tải video Facebook công khai (không bypass đăng nhập/cookie riêng tư).
Phụ thuộc app.modules.chinh_sua_video.workspace.VideoWorkspace để import video vào session.
