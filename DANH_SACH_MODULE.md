# Danh sách module — AI Video Factory

File này là chỉ mục toàn bộ bot. Mở file này để biết:
- Chức năng nằm ở thư mục nào (backend + frontend + data).
- Nếu chức năng nào lỗi thì cần gửi đúng thư mục nào cho người sửa — **không cần gửi cả dự án**.
- Lệnh test nhanh (smoke test) cho từng module.

Chi tiết đầy đủ hơn nằm trong `README_MODULE.md` và `MODULE_STATUS.md` bên trong từng thư mục.

**3 loại trạng thái**: `ĐANG DÙNG THẬT` (chức năng thật, có thể lỗi khi dùng), `KHUNG CHƯA TRIỂN
KHAI` (chỉ có thư mục + README, chưa có logic), `CORE DÙNG CHUNG` (không phải 1 "chức năng", là hạ
tầng nhiều module khác phụ thuộc vào).

--------------------------------------------------

==================================================
NHÂN VẬT 2D
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/nhan_vat_2d/

FRONTEND:
web/modules/nhan_vat_2d/

DATA:
data/character_2d_addon/ (tên thư mục data giữ nguyên, xem ghi chú cuối file)

FILE CHÍNH:
service.py (điều phối), image_runtime.py (chạy Diffusers), 28 file gate/lock/quality khác — xem
README_MODULE.md để biết vai trò từng file.

API:
Xem app/modules/nhan_vat_2d/api_nhan_vat_2d.py

PHỤ THUỘC:
Không phụ thuộc module chức năng khác. Handoff sang nhan_vat_3d ở tầng frontend (nút "dùng ảnh
này để tạo 3D"), không phải phụ thuộc Python.

LỆNH TEST NHANH:
pytest -q tests/smoke/test_nhan_vat_2d_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/nhan_vat_2d/
- web/modules/nhan_vat_2d/

KHÔNG CẦN GỬI:
- nhan_vat_3d/, chinh_sua_video/, ban_do_3d/
nếu lỗi không liên quan.

==================================================
NHÂN VẬT 3D
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/nhan_vat_3d/

FRONTEND:
web/modules/nhan_vat_3d/ (nhan_vat_3d.js, ai_3d_viewer.js, ai_3d_presets.js)

DATA:
data/3d_assets/, data/models/3d/, data/runtime3d/, data/runtime_character_hd/

FILE CHÍNH:
service.py (điều phối), triposr_backend.py, hunyuan_backend.py, character_hd_backend.py (3
backend thay thế nhau), mesh_finish.py, textured_glb_export.py, workspace.py, job_manager.py.

API:
Xem app/modules/nhan_vat_3d/api_nhan_vat_3d.py — ví dụ GET /api/3d/status

PHỤ THUỘC:
- app.modules.chinh_sua_video.ffmpeg_tools (xuất video turntable)
- app.modules.tao_anh_ai (sinh ảnh concept từ prompt nếu không có ảnh đầu vào)

LỆNH TEST NHANH:
pytest -q tests/smoke/test_nhan_vat_3d_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/nhan_vat_3d/
- web/modules/nhan_vat_3d/
- log lỗi 3D liên quan

KHÔNG CẦN GỬI:
- nhan_vat_2d/, nhan_vat_game_ready/, ban_do_3d/
nếu lỗi không liên quan (rig/animation/Game Ready đã tách riêng — xem module NHÂN VẬT GAME READY).

==================================================
NHÂN VẬT GAME READY
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/nhan_vat_game_ready/

FRONTEND:
web/modules/nhan_vat_game_ready/ (nhan_vat_game_ready.js, nhan_vat_game_ready.css — tách khỏi
nhan_vat_3d.js ở Phase 1.5; HTML markup vẫn nằm vật lý trong web/index.html, bọc comment
`<!-- MODULE: nhan_vat_game_ready BEGIN/END -->`)

DATA:
Dùng chung data/3d_assets/_game_ready/ qua workspace của nhan_vat_3d

FILE CHÍNH:
blender_game_ready.py (script Blender: optimize→rig→skin→animation→export), service.py
(GameReady3DService), jobs.py (GameReadyJobManager).

API:
- GET /api/3d/game-ready/status
- POST /api/3d/game-ready/jobs
- GET /api/3d/game-ready/jobs/{job_id}

PHỤ THUỘC:
- Nhận asset_id trỏ vào Model3DWorkspace (thuộc nhan_vat_3d) — chỉ đọc file, không import logic
  dựng mesh.
- Frontend gọi window.AIVF3D.getLastAssetId() và window.AIVF3DViewer.show() (2 API mỏng, không
  duplicate code).

LỆNH TEST NHANH:
pytest -q tests/smoke/test_nhan_vat_game_ready_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/nhan_vat_game_ready/
- web/modules/nhan_vat_game_ready/
- (nếu animation không hiển thị trong viewer: thêm web/modules/nhan_vat_3d/ai_3d_viewer.js)

KHÔNG CẦN GỬI:
- nhan_vat_2d/, ban_do_3d/, do_vat_3d/
nếu lỗi không liên quan.

==================================================
BẢN ĐỒ 3D
==================================================

TRẠNG THÁI:
KHUNG CHƯA TRIỂN KHAI

BACKEND:
app/modules/ban_do_3d/ (chỉ có __init__.py + README_MODULE.md + MODULE_STATUS.md)

FRONTEND:
web/modules/ban_do_3d/ (khung)

DATA:
(chưa có)

FILE CHÍNH:
(chưa có — xem roadmap trong README_MODULE.md)

API:
(chưa có)

PHỤ THUỘC:
Roadmap: sẽ gọi do_vat_3d qua interface/API để lấy asset lẻ, không copy code, không bake chết
asset vào map generator.

LỆNH TEST NHANH:
pytest -q tests/smoke/test_ban_do_3d_smoke.py

KHI LỖI CẦN GỬI:
(chưa có gì để lỗi)

KHÔNG CẦN GỬI:
(N/A)

==================================================
ĐỒ VẬT 3D
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/do_vat_3d/

FRONTEND:
web/modules/do_vat_3d/ (panel #panel-dovat3d + card Home nằm trong web/index.html, bọc comment
MODULE: do_vat_3d BEGIN/END)

DATA:
data/do_vat_3d/assets/ (asset hoàn thành), data/do_vat_3d/_jobs/ (job), model cache dùng chung
data/models/3d/ với nhan_vat_3d

FILE CHÍNH:
dich_vu_do_vat_3d.py (điều phối, gọi lại Local3DService của nhan_vat_3d — KHÔNG duplicate engine;
Phase 1.6.1: thêm stage enforce poly target + texture timeout + to_mau_lai retry), chon_engine.py
(tự chọn TripoSR/Character-HD theo độ phức tạp category + quality, tính poly_target_cho()),
cau_hinh_do_vat.py (13 category, 3 quality preset, 3 texture preset, poly floor theo category,
texture timeout theo texture_quality), kiem_tra_do_vat.py (validate GLB thuần stdlib, không cần
trimesh/Blender), toi_uu_do_vat.py (chuẩn hoá pivot cho nhánh character_hd + toi_uu_so_mat() enforce
poly target với fallback/bbox-safety), hop_dong_asset.py (contract GameAsset3D + metadata poly cho
ban_do_3d đọc sau này), quan_ly_job.py (job nền + GPU lock + partial_success + retry_texture).

API:
GET /api/do-vat-3d/status (kèm gpu_queue), GET /api/do-vat-3d/categories, POST /api/do-vat-3d/create,
POST /api/do-vat-3d/create-from-prompt, GET /api/do-vat-3d/job/{id},
POST /api/do-vat-3d/job/{id}/cancel, POST /api/do-vat-3d/job/{id}/retry-texture (Phase 1.6.1),
GET /api/do-vat-3d/view/{asset_id}, GET /api/do-vat-3d/output/{asset_id}, GET /api/do-vat-3d/assets

PHỤ THUỘC:
- app.modules.nhan_vat_3d.service.Local3DService (engine TripoSR/Character-HD — tái dùng nguyên,
  không copy code).
- app.modules.nhan_vat_3d.image_preprocess (hàm chung, tham số vertical_bias mới thêm — tương
  thích ngược 100%, không đổi hành vi nhan_vat_3d).
- app.modules.nhan_vat_3d.mesh_finish (gọi lại qua subprocess để chuẩn hoá pivot cho Character-HD).
- app.modules.nhan_vat_3d.mesh_decimate (Phase 1.6.1, mới - gọi lại qua subprocess để enforce poly
  target, tái dùng thuật toán vertex-clustering của mesh_optimize_light.py, KHÔNG dependency mới).
- app.modules.tao_anh_ai (sinh ảnh concept khi tạo từ prompt — KHÔNG dùng nhan_vat_2d).
- app.core.shared_services.heavy_gpu_job_lock (giới hạn 1 job nặng cùng lúc — Phase 1.6; Phase
  1.6.1 nối thêm nhan_vat_3d.job_manager vào cùng lock qua adapter mỏng, không rewrite Character 3D).

LỆNH TEST NHANH:
pytest -q tests/smoke/test_do_vat_3d_smoke.py
pytest -q tests/test_do_vat_3d_unit.py

KHI LỖI CẦN GỬI:
- app/modules/do_vat_3d/
- web/modules/do_vat_3d/
- data/do_vat_3d/_jobs/<job_id>/job.json và progress.log của job lỗi

KHÔNG CẦN GỬI:
- nhan_vat_2d/, nhan_vat_game_ready/, ban_do_3d/
nếu lỗi không liên quan. Nếu nghi ngờ lỗi ở chính engine TripoSR/Hunyuan3D dùng chung, gửi thêm
app/modules/nhan_vat_3d/.

==================================================
TẠO ẢNH AI
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/tao_anh_ai/

FRONTEND:
web/modules/tao_anh_ai/

DATA:
data/ai_images/, model cache data/models/image/

FILE CHÍNH:
service.py (LocalImageService), upscale.py, workspace.py, job_manager.py.

API:
Xem app/modules/tao_anh_ai/api_tao_anh_ai.py — ví dụ POST /api/ai-image/generate

PHỤ THUỘC:
app.modules.chinh_sua_video.workspace.VideoWorkspace (import ảnh AI vào session editor)

LỆNH TEST NHANH:
pytest -q tests/smoke/test_tao_anh_ai_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/tao_anh_ai/
- web/modules/tao_anh_ai/

KHÔNG CẦN GỬI:
- nhan_vat_2d/, nhan_vat_3d/
nếu lỗi không liên quan.

==================================================
CHỈNH SỬA ẢNH
==================================================

TRẠNG THÁI:
KHUNG CHƯA TRIỂN KHAI

BACKEND:
app/modules/chinh_sua_anh/ (chỉ có __init__.py + README_MODULE.md + MODULE_STATUS.md)

FRONTEND:
web/modules/chinh_sua_anh/ (khung)

DATA:
(chưa có)

FILE CHÍNH:
(chưa có)

API:
(chưa có)

PHỤ THUỘC:
Không được nhét logic sinh ảnh AI vào đây khi triển khai — đã có ở tao_anh_ai.

LỆNH TEST NHANH:
pytest -q tests/smoke/test_chinh_sua_anh_smoke.py

KHI LỖI CẦN GỬI:
(chưa có gì để lỗi)

KHÔNG CẦN GỬI:
(N/A)

==================================================
CHỈNH SỬA VIDEO
==================================================

TRẠNG THÁI:
CORE DÙNG CHUNG

BACKEND:
app/modules/chinh_sua_video/ — nhiều module khác import trực tiếp ffmpeg_tools.py / probe.py /
errors.py / workspace.py từ đây (am_nhac, phu_de, tai_video, lam_sach_video, tao_anh_ai,
nhan_vat_3d).

FRONTEND:
web/core/app.js (logic editor chính) + web/modules/chinh_sua_video/emoji_picker.js

DATA:
data/editor_sessions/

FILE CHÍNH:
workspace.py (VideoWorkspace — dùng chung), ffmpeg_tools.py (dùng chung), probe.py (dùng chung),
errors.py (dùng chung), cut.py, merge.py, render.py, text_image.py, service.py.

API:
Xem app/modules/chinh_sua_video/api_chinh_sua_video.py — /api/editor/*, /api/video/cut,
/api/video/merge. (Lưu ý: /api/health và /api/projects* KHÔNG thuộc module này — nằm ở
app/core/api_core.py vì dùng director/memory, không phải logic video editor.)

PHỤ THUỘC:
Không phụ thuộc module khác — ngược lại, bị nhiều module khác phụ thuộc (xem trên).

LỆNH TEST NHANH:
pytest -q tests/smoke/test_chinh_sua_video_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/chinh_sua_video/
- web/core/app.js
- (nếu lỗi ở module khác dùng chung workspace, gửi thêm module đó)

KHÔNG CẦN GỬI:
- nhan_vat_2d/, nhan_vat_3d/
nếu lỗi không liên quan tới việc lưu/đọc file session video.

==================================================
LÀM SẠCH VIDEO
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/lam_sach_video/

FRONTEND:
web/modules/lam_sach_video/

DATA:
data/video_cleanup_jobs/, runtime riêng data/runtime_video_cleanup/

FILE CHÍNH:
runtime.py (VideoCleanupRuntime), background_worker.py, inpaint_worker.py, job_manager.py.

API:
Xem app/modules/lam_sach_video/api_lam_sach_video.py — /api/cleanup/*

PHỤ THUỘC:
app.modules.chinh_sua_video.workspace.VideoWorkspace

LỆNH TEST NHANH:
pytest -q tests/smoke/test_lam_sach_video_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/lam_sach_video/
- web/modules/lam_sach_video/

KHÔNG CẦN GỬI:
- lam_sach_video không liên quan tới nhan_vat_3d/character HD (runtime riêng biệt hoàn toàn).

==================================================
TẢI VIDEO
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/tai_video/

FRONTEND:
web/modules/tai_video/

DATA:
data/facebook_downloads/

FILE CHÍNH:
downloader.py (FacebookVideoDownloader), job_manager.py (FacebookVideoJobManager).

API:
Xem app/modules/tai_video/api_tai_video.py — /api/facebook-video/*

PHỤ THUỘC:
app.modules.chinh_sua_video.workspace.VideoWorkspace (import video tải về vào session)

LỆNH TEST NHANH:
pytest -q tests/smoke/test_tai_video_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/tai_video/
- web/modules/tai_video/

KHÔNG CẦN GỬI:
- các module AI khác nếu lỗi chỉ là link Facebook không tải được.

==================================================
PHỤ ĐỀ
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/phu_de/ (gồm cả dịch thuật — translate_local cũ đã gộp vào thành dich_thuat.py)

FRONTEND:
web/modules/phu_de/

DATA:
Model cache data/models/whisper/

FILE CHÍNH:
service.py (LocalCaptionService, Whisper), audio_extract.py, group_words.py, dich_thuat.py
(LocalTranslationService, Argos Translate).

API:
Xem app/modules/phu_de/api_phu_de.py — /api/editor/{id}/captions/transcribe, /api/captions/translate

PHỤ THUỘC:
app.modules.chinh_sua_video.workspace.VideoWorkspace (lấy audio từ session)

LỆNH TEST NHANH:
pytest -q tests/smoke/test_phu_de_smoke.py

KHI LỖI CẦN GỬI:
- app/modules/phu_de/
- web/modules/phu_de/

KHÔNG CẦN GỬI:
- cong_cu_van_ban/ trừ khi lỗi liên quan preset style chữ.

==================================================
ÂM NHẠC
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/am_nhac/

FRONTEND:
web/modules/am_nhac/

DATA:
data/music_library/

FILE CHÍNH:
library.py (LocalMusicLibrary), clip_selector.py, mixer.py (mix_music).

API:
Xem app/modules/am_nhac/api_am_nhac.py — /api/music/*

PHỤ THUỘC:
app.modules.chinh_sua_video.workspace.VideoWorkspace

LỆNH TEST NHANH:
(chưa có smoke test riêng — không nằm trong danh sách bắt buộc Phase 1.5)

KHI LỖI CẦN GỬI:
- app/modules/am_nhac/
- web/modules/am_nhac/

KHÔNG CẦN GỬI:
- các module video/3D khác.

==================================================
CÔNG CỤ VĂN BẢN
==================================================

TRẠNG THÁI:
ĐANG DÙNG THẬT

BACKEND:
app/modules/cong_cu_van_ban/ (catalog preset chữ, không dùng AI)

FRONTEND:
web/modules/cong_cu_van_ban/

DATA:
(không có — dữ liệu là hằng số Python trong catalog.py)

FILE CHÍNH:
catalog.py (list_presets, get_preset)

API:
GET /api/text/presets

PHỤ THUỘC:
Không phụ thuộc module nào. Bị phu_de gọi ở tầng frontend để lấy preset chữ.

LỆNH TEST NHANH:
(chưa có smoke test riêng — không nằm trong danh sách bắt buộc Phase 1.5)

KHI LỖI CẦN GỬI:
- app/modules/cong_cu_van_ban/
- web/modules/cong_cu_van_ban/

KHÔNG CẦN GỬI:
- module khác, module này độc lập hoàn toàn.

==================================================
HẠ TẦNG DÙNG CHUNG (app/core/ + web/core/)
==================================================

TRẠNG THÁI:
CORE DÙNG CHUNG

BACKEND:
app/core/ — config.py (settings/path), shared_services.py (job cancel dùng chung, dependency
status AI local), module_registry.py (DirectorAI + catalog module), api_core.py (health/
projects), api_settings.py, api_system.py, api_job_control.py.
app/storage/ — database.py, project_memory.py (giữ nguyên vị trí, đã sạch từ trước).

FRONTEND:
web/core/ — app.js (Studio core/layer/timeline), task_progress.js (thanh tiến trình dùng chung),
home_screen.js (màn hình Home), settings.js (cài AI local).

DATA:
data/factory.db, data/models/ (cache chung)

FILE CHÍNH:
Xem trên.

API:
GET /api/health, POST/GET /api/projects*, GET/POST /api/settings/*, GET/POST /api/system/*,
POST /api/jobs/cancel-all

PHỤ THUỘC:
Không phụ thuộc module chức năng nào — mọi module chức năng phụ thuộc vào đây (config, cancel
job, dependency status).

LỆNH TEST NHANH:
python -c "import app.main"

KHI LỖI CẦN GỬI:
- app/core/
- web/core/
- app/storage/
CHỈ khi lỗi thật sự nằm ở phần dùng chung (vd tất cả module đều lỗi giống nhau, hoặc trang chủ
không mở được, hoặc nút "Dừng tất cả" không hoạt động).

KHÔNG CẦN GỬI:
- bất kỳ module chức năng nào, trừ khi lỗi lan sang do dùng chung service.

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
5. **Phase 1.5 (đã xong)**: Game Ready đã tách hoàn toàn khỏi frontend nhan_vat_3d.js — xem
   module NHÂN VẬT GAME READY ở trên. Nút điều khiển animation (Idle/Run/Attack/Stop) vẫn ở lại
   `web/modules/nhan_vat_3d/ai_3d_viewer.js` vì đó là tính năng viewer dùng chung cho mọi GLB có
   animation, không phải logic riêng của Game Ready.
6. **Smoke test**: chạy toàn bộ bằng `pytest -q tests/smoke/`. Mỗi file chạy trong vài giây,
   không tải model AI nặng, không dựng 3D thật, không chạy Blender thật, không render video thật.
