# Module: Cắt video (cat_video)

## 1. Chức năng
Cắt 1 đoạn video (frame-accurate, H.264/AAC) từ điểm start đến end. Tách ra thành module độc
lập từ `chinh_sua_video` ngày 2026-08-31 theo yêu cầu tách gọn từng mục riêng (map ra map, 2D
ra 2D, 3D ra 3D, video ra từng thao tác riêng).

## 2. File chính
- `errors.py` — `CatVideoError`, `FFmpegNotFoundError`, `InvalidVideoRequest` (copy riêng, KHÔNG
  import từ `chinh_sua_video.errors`).
- `ffmpeg_tools.py` — wrapper chạy ffmpeg (`run_tool`, `ffmpeg_bin`) (copy riêng).
- `probe.py` — đọc metadata video (`probe_video`) (copy riêng).
- `service.py` — `cut_video()`: engine cắt thật, chỉ phụ thuộc 2 file trên trong cùng module.
- `schemas.py` — `VideoCutRequest` (cắt độc lập theo path), `EditorCutRequest` (cắt trong 1
  session editor).
- `api_cat_video.py` — route API.

## 3. API thuộc module
- `POST /api/video/cut` — cắt độc lập theo `source`/`output` path, không cần session.
- `POST /api/editor/{session_id}/cut` — cắt trong 1 session editor đang mở (dùng chung
  `app.state.video_workspace` từ `chinh_sua_video` để lưu version/undo — xem mục 6).

## 4. Input
`source` (đường dẫn video) + `start`/`end` (giây); hoặc `session_id` của 1 phiên editor đang mở.

## 5. Output
File video đã cắt (H.264/AAC, `.mp4`).

## 6. Phụ thuộc module khác
- Engine cắt thật (`service.py`, `probe.py`, `ffmpeg_tools.py`, `errors.py`) — **hoàn toàn độc
  lập**, không import gì từ `chinh_sua_video`.
- Route `/api/editor/{session_id}/cut` — có đọc `app.state.video_workspace` (từ
  `chinh_sua_video.workspace.VideoWorkspace`) và bắt thêm `chinh_sua_video.errors.VideoEditorError`
  để trả lỗi đúng, vì session/undo/version history là hạ tầng dùng chung cho toàn bộ editor
  (cắt/ghép/render nối tiếp trên cùng 1 video) — xem `chinh_sua_video/README_MODULE.md`.
- `chinh_sua_video.service.VideoEditor.cut()` giờ gọi vào `cat_video.service.cut_video()` thay
  vì có logic cắt riêng — tránh trùng lặp engine thật giữa 2 module.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/cat_video/
```
Nếu lỗi liên quan session/undo (không phải lỗi cắt), gửi thêm `app/modules/chinh_sua_video/`.

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng — trừ `chinh_sua_video/service.py` (điểm nối 1 dòng gọi sang module này) và
`app/main.py` (đăng ký router).

## 9. Model AI / engine sử dụng
Không dùng AI — dùng ffmpeg trực tiếp.

## 10. Thư mục data/output
Dùng chung `data/editor_sessions/` khi cắt trong 1 session (qua `chinh_sua_video.workspace`);
khi cắt độc lập qua `/api/video/cut` thì ghi thẳng vào `output` path do caller chỉ định.
