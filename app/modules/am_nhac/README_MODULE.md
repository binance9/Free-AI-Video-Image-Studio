# Module: Âm nhạc (am_nhac)

## 1. Chức năng
Thư viện nhạc nền miễn phí local: tìm kiếm theo từ khoá, upload nhạc riêng, gợi ý theo
"wish" (mô tả cảm xúc/thể loại), và trộn (mix) nhạc nền vào video đang chỉnh sửa (chọn đoạn,
chỉnh volume, fade, giữ/tắt âm gốc).

## 2. File chính
- `library.py` — `LocalMusicLibrary`: index thư viện nhạc, tìm kiếm theo từ khoá, trả file preview.
- `clip_selector.py` — chọn đoạn nhạc (excerpt) thông minh theo độ dài yêu cầu.
- `mixer.py` — `mix_music()`: trộn audio vào video bằng ffmpeg.
- `api_am_nhac.py` — toàn bộ route API của module.
- `__init__.py` — export `LocalMusicLibrary`, `mix_music`.

## 3. API thuộc module
- `POST /api/music/search`
- `GET /api/music/library/{track_id}`
- `POST /api/editor/{session_id}/music/import-library`
- `POST /api/editor/{session_id}/music/upload`
- `POST /api/editor/{session_id}/music/apply`

## 4. Input
Từ khoá tìm kiếm, file nhạc upload (mp3/wav/m4a/aac/ogg/flac), hoặc track_id có sẵn trong thư viện.

## 5. Output
File audio đã lưu vào session video, hoặc video đã trộn nhạc (qua `video_workspace`).

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.workspace.VideoWorkspace` — lưu file audio vào session, tạo version
  video mới sau khi mix. Đây là dependency hợp lệ (không copy code), không phải trùng lặp.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/am_nhac/
web/modules/am_nhac/   (khi đã tách frontend)
```
Không cần gửi các module khác nếu lỗi không liên quan đến nhạc.

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Trừ khi lỗi nằm ở `chinh_sua_video/workspace.py` (chỗ lưu file/tạo version), không cần sửa module khác.

## 9. Model AI / engine sử dụng
Không dùng AI — chỉ dùng ffmpeg (qua `chinh_sua_video`) để trộn audio.

## 10. Thư mục data/output
`data/music_library/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py`
→ `settings.music_library_dir`).
