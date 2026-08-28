MODULE: tai_video_web
STATUS: ACTIVE (real test passed)
BACKEND_ENTRY: app/modules/tai_video_web/api_tai_video_web.py
FRONTEND_ENTRY: web/modules/tai_video_web/tai_video_web.js
SMOKE_TEST: pytest -q tests/smoke/test_tai_video_web_smoke.py

LAST_VERIFIED (2026-08-28, test thật bằng yt-dlp + FFmpeg thật, URL
https://www.youtube.com/watch?v=jNQXAC9IVRw):
- quality=360p, video: tải OK, probe_video xác nhận 320x240 15fps 19.014s co_audio=true,
  đưa vào VideoWorkspace thành công (session_id thật tạo được).
- audio_only=True: tải OK, xuất file .mp3 thật 457,388 bytes.
- Route /api/tai-video-web/status, /jobs (POST/GET/cancel), /jobs/{id}/file đều hoạt động qua
  TestClient thật; validate URL sai -> 400, quality sai -> 422.

KNOWN_LIMITATIONS:
- Chưa test thật video 1080p có video/audio tách stream cần FFmpeg merge thật sự (video test dùng
  quá ngắn/thấp độ phân giải nên yt-dlp trả 1 file luôn) - code path merge tái dùng y hệt
  app.modules.tai_video (Facebook), đã chạy thật trong production module đó.
- Không phải Facebook (module đó tách riêng, chỉ nhận link facebook.com/fb.watch).
