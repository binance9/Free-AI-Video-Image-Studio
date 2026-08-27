# Module: Chỉnh sửa video (chinh_sua_video)

## 1. Chức năng
Engine chỉnh sửa video lõi: cắt, ghép, render layer (chữ/ảnh/sticker/gif), quản lý session/asset
upload, undo/version history, xuất video. Đây là module **dùng chung nhiều nhất** trong dự án —
nhiều module khác (âm nhạc, phụ đề, tải video, làm sạch video, ảnh AI) import trực tiếp
`workspace.py`, `ffmpeg_tools.py`, `probe.py`, `errors.py` từ module này.

## 2. File chính
- `ffmpeg_tools.py` — wrapper chạy ffmpeg (`run_tool`, `ffmpeg_bin`) — **dùng chung bởi nhiều module khác**.
- `probe.py` — đọc metadata video (`probe_video`) — **dùng chung**.
- `errors.py` — `VideoEditorError` — **dùng chung**.
- `cut.py`, `merge.py`, `render.py`, `text_image.py` — logic cắt/ghép/render từng layer.
- `workspace.py` — `VideoWorkspace`: quản lý session, version history, asset, undo — **dùng chung
  bởi am_nhac, phu_de, tai_video, lam_sach_video, tao_anh_ai** để lưu file vào đúng session.
- `service.py` — `VideoEditor`: điều phối cut/merge/render.
- `schemas.py` — Pydantic request/response models của route trong module này.
- `api_chinh_sua_video.py` — route API của module (upload/cut/append/asset/render/undo/download,
  `/video/cut`, `/video/merge`).

## 3. API thuộc module
- `POST /api/editor/upload`, `GET /api/editor/{session_id}`, `GET /api/editor/{session_id}/media`
- `POST /api/editor/{session_id}/cut|append|asset|render|undo`, `GET .../download`
- `GET /api/editor/{session_id}/asset/{asset_id}`
- `POST /api/video/cut`, `POST /api/video/merge`

(Route `/api/health` và `/api/projects*` KHÔNG thuộc module này nữa — đã chuyển sang
`app/core/api_core.py` vì dùng `director`/`memory`, không phải logic video editor.)

## 4. Input
Video upload, thao tác cắt/ghép/layer từ UI.

## 5. Output
Video đã chỉnh sửa (session mới hoặc file export cuối `final_export.mp4`).

## 6. Phụ thuộc module khác
Không phụ thuộc module nào khác — ngược lại, đây là module **bị phụ thuộc** bởi hầu hết module
khác (xem trên). Sửa `workspace.py`/`ffmpeg_tools.py`/`probe.py`/`errors.py` ở đây có thể ảnh
hưởng nhiều module khác — cẩn thận khi sửa các file này.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/chinh_sua_video/
web/modules/chinh_sua_video/   (khi đã tách frontend)
```
Nếu lỗi liên quan tới module khác dùng chung workspace/ffmpeg (vd nhạc, phụ đề không lưu được
file), có thể cần gửi thêm module đó.

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng — đặc biệt cẩn trọng vì đây là module lõi dùng chung.

## 9. Model AI / engine sử dụng
Không dùng AI — dùng ffmpeg trực tiếp.

## 10. Thư mục data/output
`data/editor_sessions/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py` →
`settings.editor_dir`).
