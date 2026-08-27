# AI Video Factory 0.8 — Module Map

> **LƯU Ý:** File này ghi lại lịch sử trước đợt tái cấu trúc module (đường dẫn `app/api/*`,
> `app/modules/character_2d_addon`, `web/js/*`...). Các đường dẫn bên dưới **không còn đúng**.
> Xem **`DANH_SACH_MODULE.md`** ở root để có danh sách module + đường dẫn hiện tại.

Các khối tách riêng để sửa không dây chuyền (LỊCH SỬ, đã đổi tên — xem DANH_SACH_MODULE.md):

- `app/modules/video_editor/` — cắt, ghép, render video, overlay.
- `app/modules/image_ai_local/` — AI tạo/sửa ảnh local + upscale.
- `app/modules/model_3d_local/` — AI 3D local, **không chứa logic video/ảnh**.
  - `service.py` — orchestration prompt/image → backend.
  - `triposr_backend.py` — backend mặc định TripoSR.
  - `hunyuan_backend.py` — adapter backend chất lượng cao để mở rộng sau.
  - `workspace.py` — lưu GLB/preview riêng.
- `app/api/model_3d_routes.py` — API 3D riêng.
- `web/js/ai_3d.js` — UI 3D riêng.
- `app/modules/subtitle_local/` — Whisper local.
- `app/modules/translate_local/` — dịch local.
- `app/modules/music_local/` — nhạc local.
- `app/modules/text_templates/` — mẫu chữ/karaoke.

Installer cũng tách:
- `SETUP_FREE_AI.bat` — phụ đề/dịch/AI ảnh.
- `SETUP_FREE_3D.bat` — TripoSR 3D, chỉ cài khi cần.

- `web/js/ai_3d_viewer.js` — viewer GLB WebGL2 local, orbit/zoom/pan/wireframe/auto-rotate/fullscreen; không chứa logic dựng model.


## 0.8.6 Character HD
- `character_hd_backend.py`: backend Hunyuan3D-2mini riêng
- `run_character_hd.py`: process inference trong venv HD
- `install_character_hd.py`: installer riêng
- `SETUP_CHARACTER_HD.bat`: launcher setup Windows

## Facebook video import (0.8.6.8)
- `app/modules/facebook_video/downloader.py`: validate link Facebook public + yt-dlp download.
- `app/modules/facebook_video/job_manager.py`: background progress + import into editor.
- `app/api/facebook_video_routes.py`: status/start/job/file endpoints.
- `web/js/facebook_video.js`: UI "TẢI VIDEO TỪ FACEBOOK".


## Unified task progress (0.8.6.9)
- `web/js/task_progress.js`: one shared progress controller for every long-running editor/local-AI action.
- `web/app.js`: `setBusy()` now opens the shared %/elapsed-time UI; legacy actions inherit it automatically.
- `web/js/facebook_video.js`: mirrors real yt-dlp job progress into the shared UI.
- `web/js/ai_3d.js`: mirrors real 3D/paint job progress into the shared UI.
- `web/js/settings.js`: AI-local installation reports package-stage progress in the same UI.
- Synchronous endpoints that cannot expose frame/byte progress use an explicitly estimated progress curve capped below 100% until the response actually completes.

## 0.8.7.7 Video Cleanup
- `app/modules/video_cleanup/runtime.py`: runtime local riêng cho rembg/OpenCV.
- `app/modules/video_cleanup/background_worker.py`: xóa nền theo frame, xuất WebM alpha hoặc MP4 nền màu.
- `app/modules/video_cleanup/inpaint_worker.py`: xóa vùng chữ/icon cố định bằng OpenCV inpaint.
- `app/modules/video_cleanup/job_manager.py`: job + progress + đưa kết quả thành version editor.
- `app/api/video_cleanup_routes.py`: API `/api/cleanup/*`.
- `web/js/video_cleanup.js`: UI xóa nền + vẽ vùng xóa chữ/icon.
- `SETUP_VIDEO_CLEANUP_AI.bat`: cài runtime riêng, không trộn Character HD.


## Emoji picker 0.8.7.8
- `web/js/emoji_picker.js`: dữ liệu emoji, tìm kiếm, recent, raster PNG và chèn layer.
- `web/index.html`: UI tab Emoji / Sticker / GIF.
- `web/style.css`: lưới emoji kiểu khung chat.


## Home UI 0.8.7.9
- `web/js/home_screen.js`: Home/editor routing only.
- `web/index.html` + `web/style.css`: CapCut-inspired Home dashboard.
