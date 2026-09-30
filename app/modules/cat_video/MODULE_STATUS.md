MODULE:
cat_video

STATUS:
TÁCH ĐỘC LẬP TỪ chinh_sua_video (2026-08-31)

BACKEND_ENTRY:
app/modules/cat_video/api_cat_video.py

FRONTEND_ENTRY:
web/core/app.js (UI cắt video vẫn dùng chung khung editor - chưa tách frontend riêng)

SMOKE_TEST:
pytest -q tests/smoke/test_cat_video_smoke.py

HEAVY_MODELS:
Không có (dùng ffmpeg trực tiếp, copy riêng ffmpeg_tools.py/probe.py/errors.py - không import
từ chinh_sua_video)

LAST_VERIFIED:
2026-08-31

KNOWN_LIMITATIONS:
Route /api/editor/{session_id}/cut vẫn phải đọc/ghi app.state.video_workspace (từ
chinh_sua_video.workspace) vì session/undo/version history là hạ tầng dùng chung cho cả
cut/merge/render trong cùng 1 phiên chỉnh sửa - tách rời hoàn toàn session sẽ phá vỡ trải
nghiệm chỉnh sửa nối tiếp (cắt rồi ghép rồi render trên cùng 1 video). Chỉ ENGINE CẮT THẬT
(ffmpeg command, probe, error) là hoàn toàn độc lập, không còn phụ thuộc chinh_sua_video.
