MODULE:
am_nhac

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/am_nhac/api_am_nhac.py

FRONTEND_ENTRY:
web/modules/am_nhac/am_nhac.js

SMOKE_TEST:
(chưa có smoke test riêng — module không nằm trong danh sách bắt buộc của Phase 1.5)

HEAVY_MODELS:
Không có (chỉ dùng ffmpeg qua chinh_sua_video)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Phụ thuộc app.modules.chinh_sua_video.workspace.VideoWorkspace để lưu file audio vào session.
Tên file nội bộ (library.py, mixer.py, clip_selector.py) chưa đổi sang tiếng Việt (Phase 2).
