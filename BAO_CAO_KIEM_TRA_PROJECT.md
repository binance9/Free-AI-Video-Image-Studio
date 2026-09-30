# BÁO CÁO KIỂM TRA PROJECT — AI Video Factory v0.8.9.3.3

Ngày kiểm tra: 2026-09-01
Người kiểm tra: WorkBuddy AI
Trạng thái: CHỈ KIỂM TRA, KHÔNG SỬA

---

## 1. CẤU TRÚC PROJECT TỔNG QUAN

```
ai_video_factory/
├── app/                          ← BACKEND (FastAPI + Python)
│   ├── main.py                   ← File khởi động backend chính
│   ├── main_recovery.py          ← Bản backup của main.py (KHÔNG dùng)
│   ├── core/                     ← Hạ tầng dùng chung
│   │   ├── config.py             ← Settings (đường dẫn, version)
│   │   ├── api_core.py           ← /api/health, /api/projects
│   │   ├── api_job_control.py    ← /api/jobs/cancel-all
│   │   ├── api_job_logs.py       ← SSE log streaming
│   │   ├── api_settings.py       ← /api/settings
│   │   ├── api_system.py         ← /api/system
│   │   ├── job_log_broker.py     ← Broker SSE log
│   │   ├── module_registry.py    ← DirectorAI + MODULES catalog
│   │   ├── prompt_contract.py   ← Prompt priority layer (CLIP/T5)
│   │   └── shared_services.py    ← JobCancelled, GPU lock, dependency_status
│   ├── modules/                  ← 15 module chức năng
│   │   ├── tao_anh_ai/           ← Tạo ảnh 2D AI
│   │   ├── nhan_vat_2d/          ← Nhân vật 2D
│   │   ├── nhan_vat_3d/          ← Nhân vật 3D (TripoSR/Hunyuan3D)
│   │   ├── nhan_vat_game_ready/  ← Rig + animation (Blender)
│   │   ├── do_vat_3d/            ← Đồ vật 3D
│   │   ├── ban_do_3d/            ← Bản đồ HD 3D
│   │   ├── tao_video_ai/         ← Tạo video AI (CogVideoX/SVD)
│   │   ├── chinh_sua_video/      ← Chỉnh sửa video (CORE dùng chung)
│   │   ├── cat_video/            ← Cắt video
│   │   ├── chinh_sua_anh/        ← Chỉnh sửa ảnh (KHUNG RỖNG, chưa code)
│   │   ├── lam_sach_video/       ← Làm sạch video (xóa nền, inpaint)
│   │   ├── tai_video/            ← Tải video Facebook
│   │   ├── tai_video_web/        ← Tải video Web (yt-dlp)
│   │   ├── phu_de/               ← Phụ đề (Whisper) + Dịch thuật (Argos)
│   │   ├── am_nhac/              ← Âm nhạc
│   │   ├── cong_cu_van_ban/      ← Công cụ văn bản (preset chữ)
│   │   ├── ga_brain/              ← NÃO AI (Ollama, intent router, planner)
│   │   ├── ga_owner/             ← Giao diện chat + voice owner
│   │   ├── ga_maintenance/       ← Self-heal + runtime guard
│   │   ├── ai_video_director/    ← Pipeline sản xuất video tự động
│   │   └── model_3d_library.py   ← Thư viện 3D
│   ├── api/
│   │   └── model_3d_library_routes.py
│   └── storage/
│       ├── database.py
│       └── project_memory.py
├── web/                          ← FRONTEND (Vanilla JS SPA)
│   ├── index.html                ← Entry point (644 dòng, 30 script tags)
│   ├── index_recovery.html       ← Bản recovery (KHÔNG dùng chính)
│   ├── core/                     ← 22 file JS + CSS
│   │   ├── app.js                ← God Object (Studio singleton)
│   │   ├── ga_brain.js           ← AI orchestrator (monkey-patch fetch!)
│   │   ├── ga_owner.js           ← Chat UI
│   │   ├── job_terminal.js       ← SSE terminal
│   │   ├── persistent_shell.js   ← Chat/terminal resize
│   │   ├── home_screen.js       ← Home navigation
│   │   ├── task_progress.js      ← Progress overlay
│   │   ├── realtime_preview.js   ← Preview area
│   │   ├── realtime_progress.js  ← Job polling helper
│   │   ├── image_prompt_input.js ← Reusable prompt input
│   │   ├── settings.js           ← AI local installation
│   │   ├── kill_bot.js           ← Shutdown button
│   │   └── khung_xem_truoc_chung.js ← DEAD CODE (no-op shim)
│   ├── modules/                  ← JS module theo backend
│   └── stickers/                 ← PNG sticker pack
├── START_VIDEO_FACTORY.py        ← FILE KHỞI ĐỘNG CHÍNH
├── START_VIDEO_FACTORY.bat       ← Launcher .bat
├── main.py                       ← Tkinter Gà Maintenance (RIÊNG BIỆT)
├── agent.py                      ← Agent cho Gà Maintenance (Ollama)
├── gui.py                        ← Tkinter GUI cho Gà Maintenance
├── tools.py                      ← Tools cho Gà Maintenance
├── speech_vi.py                  ← Voice listener tiếng Việt
├── maintenance.py                ← System maintenance logic
├── config.json                   ← Config cho Gà Maintenance
├── requirements.txt              ← Dependencies backend
├── requirements_local_ai.txt     ← Dependencies AI local
├── requirements_video_cleanup.txt← Dependencies cleanup
├── requirements_before_gpu_fix.txt ← Pinned versions (120 gói)
├── tests/smoke/                  ← 18 smoke test
├── tests/                        ← 40+ unit test
└── [NHIỀU THƯ MỤC BACKUP/PAYLOAD - xem phần 6]
```

---

## 2. FILE KHỞI ĐỘNG CHÍNH

### Backend (Web App chính):
- **`START_VIDEO_FACTORY.py`** — Đây là file khởi động chính
  - Tìm cổng trống 8123-8199
  - Khởi động `uvicorn.run(app, ...)` với app từ `app/main.py`
  - Mở trình duyệt tự động
  - Kiểm tra nếu đã có instance chạy rồi thì chỉ mở browser
- **`START_VIDEO_FACTORY.bat`** — Gọi VBS ẩn, rồi gọi `START_VIDEO_FACTORY.py`
- **`app/main.py`** — FastAPI app factory, nạp toàn bộ 20+ router + service

### Gà Maintenance (Tkinter Desktop app, RIÊNG BIỆT):
- **`main.py`** (root) — Tkinter GUI app, dùng `gui.py`, `agent.py`, `tools.py`
- **`BAT_DAU_GA_AI.bat`** — Launcher cho Gà Maintenance
- Chạy bằng `.venv\Scripts\pythonw.exe main.py`

**LƯU Ý:** `main.py` ở root và `app/main.py` là 2 file KHÁC NHAU:
- `main.py` (root) = Gà Maintenance Tkinter GUI (desktop widget)
- `app/main.py` = FastAPI web backend (AI Video Factory chính)

---

## 3. FRONTEND / BACKEND / MODULE AI

### Backend Architecture:
- **Framework:** FastAPI + Uvicorn
- **AI Model:** Ollama (qwen3:8b fast, qwen3:30b main)
- **Image AI:** Diffusers (Stable Diffusion v1.5)
- **3D AI:** TripoSR + Hunyuan3D-2mini (Character-HD)
- **Video AI:** CogVideoX + SVD (Stable Video Diffusion)
- **Video Processing:** FFmpeg (qua subprocess)
- **Subtitle:** faster-whisper (local)
- **Translation:** argostranslate (local)
- **Background Removal:** rembg + OpenCV + onnxruntime
- **Voice:** sounddevice + speech_recognition (Google API)
- **Database:** SQLite (factory.db)
- **Job Queue:** In-process threading + GPU lock

### Frontend Architecture:
- **Loại:** Single-Page Application (SPA), vanilla JS, không framework
- **Pattern:** God Object (`window.Studio`) + Plugin Modules (IIFE)
- **Load:** 30 `<script>` tags trong index.html, thứ tự cứng
- **Backend comms:** REST polling + SSE (Server-Sent Events)
- **Chat/Terminal:** ga_owner.js + ga_brain.js + job_terminal.js

### Module AI:
| Module | Backend | Frontend | Trạng thái |
|--------|---------|----------|------------|
| Tạo ảnh 2D AI | tao_anh_ai/ | tao_anh_ai.js | ĐANG DÙNG THẬT |
| Tạo ảnh 3D | nhan_vat_3d/ | nhan_vat_3d.js | ĐANG DÙNG THẬT |
| Character 2D | nhan_vat_2d/ | nhan_vat_2d.js | ĐANG DÙNG THẬT |
| Model 3D | nhan_vat_3d/ (TripoSR/Hunyuan) | ai_3d_viewer.js | ĐANG DÙNG THẬT |
| Map 3D | ban_do_3d/ | ban_do_3d.js | ĐANG DÙNG THẬT (V1: 2D tile) |
| Video AI | tao_video_ai/ | tao_video_ai.js | ĐANG DÙNG THẬT |
| Chỉnh sửa ảnh | chinh_sua_anh/ | (khung) | KHUNG RỖNG, CHƯA CODE |
| Chỉnh sửa video | chinh_sua_video/ | app.js + emoji_picker.js | CORE DÙNG CHUNG |
| Download video | tai_video/ + tai_video_web/ | tai_video.js + tai_video_web.js | ĐANG DÙNG THẬT |
| Làm sạch video | lam_sach_video/ | lam_sach_video.js | ĐANG DÙNG THẬT |
| Giao diện chat | ga_brain/ + ga_owner/ | ga_brain.js + ga_owner.js | ĐANG DÙNG THẬT |
| Terminal/PowerShell | job_terminal.js + persistent_shell.js | SSE stream | ĐANG DÙNG THẬT |
| Game Ready 3D | nhan_vat_game_ready/ | nhan_vat_game_ready.js | ĐANG DÙNG THẬT |
| Đồ vật 3D | do_vat_3d/ | do_vat_3d.js | ĐANG DÙNG THẬT |
| AI Video Director | ai_video_director/ | ai_video_director.js | ĐANG DÙNG THẬT |
| Self-heal | ga_maintenance/ | (qua ga_brain) | ĐANG DÙNG THẬT |

---

## 4. DEPENDENCY VÀ CÁCH KHỞI ĐỘNG

### Requirements files (4 file):
1. **`requirements.txt`** — Minimal: fastapi, uvicorn, pydantic, Pillow, yt-dlp, numpy, python_speech_features
2. **`requirements_local_ai.txt`** — AI heavy: torch, diffusers, transformers, faster-whisper, argostranslate
3. **`requirements_video_cleanup.txt`** — rembg, opencv, onnxruntime-gpu
4. **`requirements_before_gpu_fix.txt`** — Pinned versions (120 gói, bao gồm cả ccxt, playwright, spacy, stanza...)

### Khởi động:
1. **Web backend:** `START_VIDEO_FACTORY.bat` → VBS → `START_VIDEO_FACTORY.py` → `uvicorn(app/main.py)` → mở browser
2. **Gà Maintenance:** `BAT_DAU_GA_AI.bat` → `.venv\pythonw.exe main.py` → Tkinter widget
3. **Cổng:** 8123-8199 (tự tìm cổng trống)
4. **URL:** `http://127.0.0.1:{port}/?studio=0.8.9.3.3&ga=v9.7`

### Dependency AI ngoài:
- **Ollama** phải chạy ở `http://127.0.0.1:11434` (model qwen3:8b + qwen3:30b)
- **TripoSR** tại `tools/external/TripoSR/`
- **Blender** (cho Game Ready rig/animation)
- **FFmpeg** (qua subprocess, không có trong requirements)

---

## 5. LỖI PHÁT HIỆN ĐƯỢC

### LỖI NGHIÊM TRỌNG (Cần ưu tiên):

**L1. `ga_brain.js` monkey-patch `window.fetch` toàn cục**
- `ga_brain.js` ghi đè `window.fetch` để tự động chặn mọi HTTP request, parse response, và auto-register job monitor
- Đây là side-effect toàn cộc ảnh hưởng đến MỌI fetch call trong app, không chỉ ga_brain
- Gây khó debug, khó lý đoán hành vi, có thể gây conflict khi nhiều module cùng tạo job
- **Rủi ro:** Nếu URL pattern match sai, có thể parse response sai → UI state conflict

**L2. `app/main.py` vs `app/main_recovery.py` — Trùng lặp gần như 100%**
- `main_recovery.py` là bản sao của `main.py` nhưng thiếu 5 router (ga_owner, ga_brain, ga_maintenance, ai_video_director, tao_video_ai)
- `main_recovery.py` serve `index_recovery.html` thay vì `index.html`
- Không được import hay sử dụng bởi START_VIDEO_FACTORY.py
- **Rủi ro:** Nhầm lẫn, sửa nhầm file

**L3. 5 cơ chế polling khác nhau (trùng lặp code lớn)**
1. `setInterval` + `activeJob` — tai_video.js, tai_video_web.js, tao_video_ai.js
2. `while(true)` + `await setTimeout` — lam_sach_video.js
3. Recursive `setTimeout` — nhan_vat_3d.js, nhan_vat_game_ready.js, ban_do_3d.js
4. `AIVFRealtimeProgress.poll()` — chỉ tao_anh_ai.js dùng
5. `ga_brain.js monitorJob()` — polling riêng với `await setTimeout(1500)`
- **Rủi ro:** Code trùng, khó bảo trì, dễ race condition

**L4. `tai_video.js` vs `tai_video_web.js` — Gần như identical**
- Cùng structure: `showProgress()`, `setProgress()`, `setButtonBusy()`, `loadStatus()`, `pollJob()`, `startDownload()`
- Khác chỉ ở API endpoint và element ID prefix
- **Rủi ro:** Sửa bug ở 1 file quên sửa file kia

**L5. `requirements.txt` thiếu nhiều dependency thật**
- Chỉ có 7 gói (fastapi, uvicorn, pydantic, python-multipart, Pillow, yt-dlp, numpy, python_speech_features)
- Thiếu: requests (agent.py import), sounddevice (speech_vi.py), speech_recognition (speech_vi.py), psutil (maintenance.py), scipy (nhiều module)
- Có 3 file requirements khác + 1 file pinned 120 gói
- **Rủi ro:** Cài mới không chạy được, thiếu gói

**L6. Progress UI phân mảnh (4 hệ thống song song)**
- `TaskProgress` (overlay)
- `AIVFRealtimePreview` (preview area)
- `AIVFJobTerminal` (SSE terminal + progress %)
- Per-module progress bars (mỗi module có progressStage/progressPct/progressBar riêng)
- **Rủi ro:** Hiển thị tiến trình không nhất quán

### LỖI TRUNG BÌNH:

**L7. `khung_xem_truoc_chung.js` là DEAD CODE**
- Tất cả method là no-op
- Vẫn được load trong index.html
- **Rủi ro:** Tăng load time, gây nhầm lẫn

**L8. `chinh_sua_anh/` module rỗng**
- Chỉ có `__init__.py` (0 byte), `README_MODULE.md`, `MODULE_STATUS.md`
- Không có service, api, hay logic nào
- Đã có slot trong index.html nhưng không có code
- **Rủi ro:** Người dùng tưởng tính năng đã có

**L9. `do_vat_3d` tái sử dụng `Local3DService` của `nhan_vat_3d` — coupling chặt**
- `DoVat3DService` gọi trực tiếp `Local3DService` (không qua interface/API)
- Cùng dùng `Model3DWorkspace`, `image_preprocess`, `mesh_finish`, `mesh_decimate`
- **Rủi ro:** Sửa nhan_vat_3d có thể vỡ do_vat_3d

**L10. `collector_source_ga.py` và `install_ga_into_factory.py` ở root**
- Đây là script utility, không phải runtime code
- `install_ga_into_factory.py` patch `app/main.py` bằng string replace
- **Rủi ro:** Nếu chạy lại sẽ chèn duplicate import line

**L11. 15+ file INSTALL_*.py và VERIFY_*.py ở root**
- INSTALL_AI_VIDEO_DIRECTOR.py qua V6_5_1, V7_MEMORY
- VERIFY_TAO_ANH_AI_V6_5_2.py, V6_5_3, V6_5_4
- Đây là patch installer, đã chạy xong, không cần nữa
- **Rủi ro:** Nhầm lẫn, chạy nhầm installer cũ

**L12. Nhiều thư mục backup/payload không cần thiết ở root**
- `_backup_before_modular_refactor/` (35 file)
- `_backup_before_3d_library/` (3 file)
- `_backup_before_ga_owner_20260828_164837/` (3 file)
- `_backup_before_map_hd_install/` (3 file)
- `_GA_PATCH_PAYLOAD/` (6 file)
- `_PATCH_PAYLOAD/` (20 file)
- `_fps_patch/` (2 file)
- `_ui_payload/` (2 file)
- `_3d_library_payload/` (3 file)
- `_v7_patch/` (4 file)
- `_V10_SOURCE_NHE/` (293 file — bản sao gần full project!)
- `_director_v3_payload/` (42 file)
- `_BACKUP_GENERAL_SEMANTIC_PROMPT_V6_5_7_20260901_224750/` (2 file)
- `_BACKUP_PROMPT_CONTRACT_V6_5_1_20260901_192312/` (8 file)
- `_BACKUP_TAO_ANH_AI_V6_5_2/`, `V6_5_3/`, `V6_5_4/` (1-3 file mỗi cái)
- `_BACKUP_VIDEO_CFR_QA_V6_5_5_20260901_221547/` (3 file)
- `_verify_model_cache/`
- **Rủi ro:** Làm rối cấu trúc project, tốn dung lượng, dễ nhầm code

**L13. Nhiều file .bak trong web/ và app/**
- `web/index.html.before_ai_video_director.bak`
- `web/index.html.before_ai_video_director_v3.bak`
- `web/index.html.before_ai_video_director_v64.bak`
- `web/index.html.before_ai_video_director_v641.bak`
- `web/index.html.before_v6_3_1_ui.bak`
- `app/main.py.before_ai_video_director.bak`
- `app/main.py.before_ai_video_director_v3.bak`
- `app/main.py.before_ai_video_director_v64.bak`
- `app/main.py.before_ai_video_director_v641.bak`
- **Rủi ro:** Nhầm lẫn file nào là file thật

**L14. `MODULE_MAP.md` đã lỗi thời**
- Dòng 3-5 ghi rõ: "File này ghi lại lịch sử trước đợt tái cấu trúc module. Các đường dẫn bên dưới không còn đúng"
- Vẫn còn trong project

**L15. `agent.py` import `requests` nhưng không có trong `requirements.txt`**
- `agent.py` dòng 3: `import requests`
- `requirements.txt` không có `requests`
- Chỉ có trong `requirements_before_gpu_fix.txt` (pinned)

**L16. `config.json` ở root cho Gà Maintenance, không cho backend**
- `config.json` chứa cấu hình Ollama cho `main.py` (Gà Maintenance Tkinter)
- Backend `app/core/config.py` dùng `Settings` dataclass riêng, không đọc `config.json`
- **Rủi ro:** Nhầm lẫn config nào cho ai

### LỖI NHẸ:

**L17. Nhiều file .txt status/doc ở root (150+ file)**
- BUILD_STATUS_0_8_1.txt đến 0_8_7_8.txt
- CHARACTER_HD_0_8_6.txt và 8 file con
- DOC_V5_2_NO_SPAM.txt, DOC_V6_GIAO_TIEP_THONG_MINH.txt, etc.
- README_V6_3_1.txt, README_V10_3.txt, etc.
- TEST_PASS_V9_3.txt đến V9_7.txt
- **Rủi ro:** Rối project, khó tìm file quan trọng

**L18. `__pycache__` trong `app/modules/chinh_sua_anh/`**
- Module rỗng nhưng có `__pycache__` → từng có code rồi xóa

**L19. Smoke test cho `chinh_sua_anh` tồn tại nhưng module rỗng**
- `tests/smoke/test_chinh_sua_anh_smoke.py` tồn tại
- `app/modules/chinh_sua_anh/` chỉ có `__init__.py` 0 byte

---

## 6. CÁC THƯ MỤC BACKUP/PAYLOAD CHẾT (KHÔNG ĐƯỢC IMPORT)

| Thư mục | Số file | Mục đích |
|---------|---------|----------|
| _V10_SOURCE_NHE/ | 293 | Bản sao gần full project (app + web) |
| _backup_before_modular_refactor/ | 35 | Backup trước refactor |
| _director_v3_payload/ | 42 | Patch payload cho AI Video Director V3 |
| _PATCH_PAYLOAD/ | 20 | Patch payload (prompt_contract, service files) |
| _GA_PATCH_PAYLOAD/ | 6 | Patch payload cho Gà Owner |
| _BACKUP_PROMPT_CONTRACT_V6_5_1_*/ | 8 | Backup trước prompt contract V6.5.1 |
| _BACKUP_TAO_ANH_AI_V6_5_2/ | 1 | Backup trước tao_anh_ai V6.5.2 |
| _BACKUP_TAO_ANH_AI_V6_5_3/ | 1 | Backup trước tao_anh_ai V6.5.3 |
| _BACKUP_TAO_ANH_AI_V6_5_4/ | 1 | Backup trước tao_anh_ai V6.5.4 |
| _BACKUP_VIDEO_CFR_QA_V6_5_5/ | 3 | Backup trước video CFR QA |
| _BACKUP_GENERAL_SEMANTIC_PROMPT_V6_5_7_*/ | 2 | Backup trước general semantic prompt |
| _backup_before_3d_library/ | 3 | Backup trước 3D library |
| _backup_before_ga_owner_*/ | 3 | Backup trước ga_owner |
| _backup_before_map_hd_install/ | 3 | Backup trước map HD |
| _fps_patch/ | 2 | Patch FPS fix |
| _ui_payload/ | 2 | UI payload |
| _3d_library_payload/ | 3 | 3D library payload |
| _v7_patch/ | 4 | V7 patch |
| _verify_model_cache/ | 0 | Cache verify (rỗng) |

**Tổng cộng:** ~430+ file trong các thư mục backup/payload chết.

---

## 7. FILE CẦN SỬA (THEO THỨ TỰ ƯU TIÊN)

### Phase 1 — Dọn dẹp cấu trúc (không đổi hành vi):
1. **Xóa `app/main_recovery.py`** — Bản duplicate, không dùng
2. **Xóa `web/index_recovery.html`** — Bản duplicate, không dùng
3. **Xóa `web/core/khung_xem_truoc_chung.js`** — Dead code no-op
4. **Xóa `web/core/khung_xem_truoc_chung.css`** — CSS cho dead code
5. **Xóa các file `.bak`** trong `web/` và `app/` (10 file)
6. **Xóa `MODULE_MAP.md`** — Đã tự ghi "không còn đúng"
7. **Gom 15+ thư mục `_backup_*`, `_PATCH_PAYLOAD`, `_GA_PATCH_PAYLOAD`, `_V10_SOURCE_NHE`, v.v.** vào 1 thư mục `_archive/` hoặc xóa hết (cần xác nhận user)

### Phase 2 — Sửa dependency:
8. **Gộp `requirements.txt`** — Thêm `requests`, `sounddevice`, `speech_recognition`, `psutil`, `scipy` vào requirements.txt chính
9. **Xóa `requirements_before_gpu_fix.txt`** — 120 gói pinned, bao gồm cả ccxt/playwright/spacy không liên quan
10. **Gộp `requirements_local_ai.txt` + `requirements_video_cleanup.txt`** thành `requirements.txt` chính hoặc giữ riêng có comment rõ

### Phase 3 — Refactor frontend:
11. **Gộp `tai_video.js` + `tai_video_web.js`** thành 1 module download với parameter
12. **Tạo `pollJob()` helper chung** trong `core/app.js`, thay thế 5 cơ chế polling
13. **Tháo `ga_brain.js` fetch monkey-patch** — Thay bằng explicit `Studio.registerJob(jobId, kind)` call từ mỗi module
14. **Gộp progress UI** — Chọn 1 hệ thống progress chính (TaskProgress hoặc RealtimePreview), bỏ các per-module progress bar

### Phase 4 — Sửa backend:
15. **Xóa `collector_source_ga.py`** và **`install_ga_into_factory.py`** — Script utility đã dùng xong
16. **Xóa 15+ file `INSTALL_*.py` và `VERIFY_*.py`** ở root — Đã chạy xong
17. **Decouple `do_vat_3d` khỏi `nhan_vat_3d`** — Tạo interface chung hoặc dùng API call thay vì import trực tiếp
18. **Xóa hoặc code thật `chinh_sua_anh/`** — Module rỗng, quyết định xóa hoặc triển khai
19. **Dọn 150+ file .txt status/doc** ở root — Gom vào `docs/history/` hoặc xóa

### Phase 5 — Polish:
20. **Thêm FFmpeg vào requirements hoặc doc cài đặt** — Hiện không có trong requirements
21. **Sửa `config.json`** — Đổi tên thành `ga_maintenance_config.json` để rõ ràng
22. **Comment rõ trong `main.py` (root)** rằng đây là Gà Maintenance Tkinter, không phải backend
23. **Thêm `tools/external/TripoSR/` vào .gitignore** hoặc doc cài đặt

---

## 8. KẾ HOẠCH SỬA THEO THỨ TỰ

| Bước | Mô tả | Rủi ro | Ưu tiên |
|------|-------|--------|---------|
| 1 | Xóa file backup/payload chết (main_recovery, index_recovery, .bak files, khung_xem_truoc_chung) | Rất thấp | CAO |
| 2 | Gom thư mục backup/payload vào _archive/ | Thấp | CAO |
| 3 | Sửa requirements.txt (thêm thiếu gói) | Thấp | CAO |
| 4 | Gộp tai_video.js + tai_video_web.js | Trung bình | TRUNG BÌNH |
| 5 | Tạo pollJob() helper chung | Trung bình | TRUNG BÌNH |
| 6 | Tháo ga_brain.js fetch monkey-patch | CAO — cần test kỹ | TRUNG BÌNH |
| 7 | Gộp progress UI | Trung bình | TRUNG BÌNH |
| 8 | Decouple do_vat_3d / nhan_vat_3d | CAO — core architectural | THẤP |
| 9 | Xóa/chuyển INSTALL/VERIFY scripts | Rất thấp | CAO |
| 10 | Dọn .txt status files | Rất thấp | THẤP |
| 11 | Xử lý chinh_sua_anh (xóa hoặc code) | Thấp | THẤP |
| 12 | Polish config/docs | Rất thấp | THẤP |

---

## KẾT LUẬN

Project AI Video Factory là một hệ thống phức tạp, có kiến trúc modular hợp lý ở backend (15 module tách biệt) nhưng frontend còn nhiều trùng lặp. Vấn đề lớn nhất:

1. **ga_brain.js monkey-patch fetch** — rủi ro cao nhất, khó debug
2. **5 cơ chế polling khác nhau** — trùng lặp code lớn
3. **tai_video.js vs tai_video_web.js** — gần như identical
4. **430+ file backup/payload chết** — làm rối project
5. **requirements.txt thiếu gói** — cài mới không chạy

Tất cả các lỗi trên đều có thể sửa được, nhưng CẦN ĐƯỢC PHÉP trước khi sửa bất kỳ file nào.
