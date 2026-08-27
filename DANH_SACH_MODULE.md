# Danh sách module — AI Video Factory

File này là chỉ mục toàn bộ bot. Mở file này để biết:
- Chức năng nằm ở thư mục nào (backend + frontend).
- Nếu chức năng nào lỗi thì cần gửi đúng thư mục nào cho người sửa.
- **Không cần gửi cả dự án** — chỉ cần zip đúng 1-2 thư mục module bên dưới.

Chi tiết đầy đủ hơn (input/output, model AI dùng, phụ thuộc module khác) nằm trong
`README_MODULE.md` bên trong từng thư mục module.

Cấu trúc chung mọi module đều theo:
```
app/modules/<ten_module>/    backend (routes, service, __init__.py, README_MODULE.md)
web/modules/<ten_module>/    frontend (JS)  — nếu đã tách; một số còn dùng chung web/core/
data/<ten_thu_muc_cu>/       dữ liệu/output — TÊN THƯ MỤC VẬT LÝ GIỮ NGUYÊN như trước refactor
```

--------------------------------------------------

## NHÂN VẬT 2D (nhan_vat_2d)
Backend: `app/modules/nhan_vat_2d/` (30 file — module lớn nhất, nhiều gate/lock)
Frontend: `web/modules/nhan_vat_2d/nhan_vat_2d.js`
Data: `data/character_2d_addon/` (tên thư mục data giữ nguyên)
Khi lỗi gửi: `app/modules/nhan_vat_2d/`, `web/modules/nhan_vat_2d/`

--------------------------------------------------

## NHÂN VẬT 3D (nhan_vat_3d)
Backend: `app/modules/nhan_vat_3d/` (TripoSR, Hunyuan3D, Character-HD)
Frontend: `web/modules/nhan_vat_3d/` (nhan_vat_3d.js, ai_3d_viewer.js, ai_3d_presets.js)
Data: `data/3d_assets/`, `data/models/3d/`, `data/runtime3d/`, `data/runtime_character_hd/`
Khi lỗi gửi: `app/modules/nhan_vat_3d/`, `web/modules/nhan_vat_3d/`

--------------------------------------------------

## NHÂN VẬT GAME READY (nhan_vat_game_ready)
Backend: `app/modules/nhan_vat_game_ready/` (Blender headless: rig/skin/animation)
Frontend: **chưa tách riêng** — UI nằm trong `web/modules/nhan_vat_3d/nhan_vat_3d.js`
Data: dùng chung `data/3d_assets/_game_ready/` (qua workspace của nhan_vat_3d)
Khi lỗi gửi: `app/modules/nhan_vat_game_ready/` (+ `web/modules/nhan_vat_3d/nhan_vat_3d.js` nếu lỗi ở UI)

--------------------------------------------------

## BẢN ĐỒ 3D (ban_do_3d) — CHƯA TRIỂN KHAI
Backend: `app/modules/ban_do_3d/` (khung/skeleton)
Frontend: `web/modules/ban_do_3d/` (khung/skeleton)
Khi lỗi gửi: (chưa có gì để lỗi)

--------------------------------------------------

## ĐỒ VẬT 3D (do_vat_3d) — CHƯA TRIỂN KHAI
Backend: `app/modules/do_vat_3d/` (khung/skeleton)
Frontend: `web/modules/do_vat_3d/` (khung/skeleton)
Khi lỗi gửi: (chưa có gì để lỗi)

--------------------------------------------------

## TẠO ẢNH AI (tao_anh_ai)
Backend: `app/modules/tao_anh_ai/`
Frontend: `web/modules/tao_anh_ai/tao_anh_ai.js`
Data: `data/ai_images/`, model cache `data/models/image/`
Khi lỗi gửi: `app/modules/tao_anh_ai/`, `web/modules/tao_anh_ai/`

--------------------------------------------------

## CHỈNH SỬA ẢNH (chinh_sua_anh) — CHƯA TRIỂN KHAI
Backend: `app/modules/chinh_sua_anh/` (khung/skeleton)
Frontend: `web/modules/chinh_sua_anh/` (khung/skeleton)
Khi lỗi gửi: (chưa có gì để lỗi)

--------------------------------------------------

## CHỈNH SỬA VIDEO (chinh_sua_video)
Backend: `app/modules/chinh_sua_video/` — **module lõi dùng chung**: nhiều module khác
(âm nhạc, phụ đề, tải video, làm sạch video, tạo ảnh AI) import trực tiếp
`workspace.py` / `ffmpeg_tools.py` / `probe.py` / `errors.py` từ đây.
Frontend: `web/core/app.js` (logic editor chính nằm ở core vì là shell dùng chung) +
`web/modules/chinh_sua_video/emoji_picker.js` (layer emoji/sticker)
Data: `data/editor_sessions/`
Khi lỗi gửi: `app/modules/chinh_sua_video/`, `web/core/app.js`. Nếu lỗi chỉ ở module khác
dùng chung workspace (vd nhạc không lưu được file), gửi thêm module đó.

--------------------------------------------------

## LÀM SẠCH VIDEO (lam_sach_video)
Backend: `app/modules/lam_sach_video/` (rembg xoá nền, OpenCV inpaint)
Frontend: `web/modules/lam_sach_video/lam_sach_video.js`
Data: `data/video_cleanup_jobs/`, runtime `data/runtime_video_cleanup/`
Khi lỗi gửi: `app/modules/lam_sach_video/`, `web/modules/lam_sach_video/`

--------------------------------------------------

## TẢI VIDEO (tai_video)
Backend: `app/modules/tai_video/` (yt-dlp, chỉ video Facebook công khai)
Frontend: `web/modules/tai_video/tai_video.js`
Data: `data/facebook_downloads/`
Khi lỗi gửi: `app/modules/tai_video/`, `web/modules/tai_video/`

--------------------------------------------------

## PHỤ ĐỀ (phu_de)
Backend: `app/modules/phu_de/` (Whisper speech-to-text + Argos Translate dịch phụ đề,
`translate_local` cũ đã gộp vào đây thành `dich_thuat.py`)
Frontend: `web/modules/phu_de/phu_de.js`
Data: model cache `data/models/whisper/`
Khi lỗi gửi: `app/modules/phu_de/`, `web/modules/phu_de/`

--------------------------------------------------

## ÂM NHẠC (am_nhac)
Backend: `app/modules/am_nhac/`
Frontend: `web/modules/am_nhac/am_nhac.js`
Data: `data/music_library/`
Khi lỗi gửi: `app/modules/am_nhac/`, `web/modules/am_nhac/`

--------------------------------------------------

## CÔNG CỤ VĂN BẢN (cong_cu_van_ban)
Backend: `app/modules/cong_cu_van_ban/` (catalog preset chữ/karaoke, không dùng AI)
Frontend: `web/modules/cong_cu_van_ban/cong_cu_van_ban.js`
Khi lỗi gửi: `app/modules/cong_cu_van_ban/`, `web/modules/cong_cu_van_ban/`

--------------------------------------------------

## HẠ TẦNG DÙNG CHUNG (app/core/ + web/core/) — không phải "chức năng" riêng
Backend: `app/core/` — `config.py` (settings/path), `shared_services.py` (job cancel dùng
chung, dependency status AI local), `module_registry.py` (DirectorAI + catalog module),
`api_core.py` (health/projects), `api_settings.py`, `api_system.py`, `api_job_control.py`.
Frontend: `web/core/` — `app.js` (Studio core/layer/timeline), `task_progress.js` (thanh
tiến trình dùng chung), `home_screen.js` (màn hình Home), `settings.js` (cài AI local).
Storage: `app/storage/` — `database.py`, `project_memory.py` (giữ nguyên vị trí, đã sạch).
Khi lỗi gửi: `app/core/`, `web/core/`, `app/storage/` — CHỈ khi lỗi thật sự nằm ở phần dùng
chung (vd tất cả module đều lỗi giống nhau, hoặc trang chủ không mở được).

--------------------------------------------------

## GHI CHÚ QUAN TRỌNG

1. **`data/` KHÔNG đổi tên** ở đợt refactor này (71GB, nằm trong OneDrive — đổi tên rất rủi
   ro/chậm). Tên thư mục con trong `data/` vẫn là tên module CŨ (character_2d_addon,
   video_cleanup, ...) dù code đã đổi sang tên mới. Đây là quyết định có chủ đích, không phải
   sót.
2. **Tên file bên trong mỗi module (Phase 2, chưa làm)**: các file như `service.py`,
   `image_runtime.py`, `triposr_backend.py`... vẫn giữ tên tiếng Anh gốc. Việc đổi tên từng
   file sang tiếng Việt sẽ làm sau, từng module một, khi module đó cần sửa gì thì làm luôn lúc
   đó — để giảm rủi ro so với đổi 150+ file cùng lúc.
3. **`_backup_before_modular_refactor/`** ở root chứa bản sao 1 thư mục rác đã xác nhận chết
   (`app/app/` cũ, không được `main.py` import) — giữ lại để backup, không phải code đang
   chạy.
4. **`v13_fixwork/`** ở root là bản backup cũ không liên quan tới refactor này — không đụng
   vào, không nằm trong git (đã gitignore).
