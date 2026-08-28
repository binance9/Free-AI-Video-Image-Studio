# Module: Tải Video Web (tai_video_web)

## 1. Module dùng làm gì
Tải video từ YouTube và các trang phổ biến khác qua `yt-dlp` (khác với `app.modules.tai_video`,
module đó CHỈ hỗ trợ Facebook). Chọn chất lượng 360p/720p/1080p/tốt nhất, tải video (đưa thẳng vào
editor) hoặc chỉ audio (MP3, lưu vào thư mục output riêng). Nếu yt-dlp trả về video/audio tách
stream (thường gặp với video HD), FFmpeg tự ghép lại (`merge_output_format="mp4"`).

## 2. Backend entry
`app/modules/tai_video_web/api_tai_video_web.py` (đăng ký trong `app/main.py`).

## 3. Frontend entry
`web/modules/tai_video_web/tai_video_web.js` — file JS **tách riêng hoàn toàn**, không có logic
nào nằm trong `web/core/app.js` (chỉ có 1 dòng `toolMeta.taivideoweb` để hiển thị tiêu đề panel,
theo đúng quy ước có sẵn của mọi module khác). Markup HTML nằm trong `web/index.html`, bọc comment
`<!-- MODULE: tai_video_web BEGIN/END -->`.

## 4. API
- `GET /api/tai-video-web/status`
- `POST /api/tai-video-web/jobs` — JSON `{url, quality, audio_only}` → job dict.
- `GET /api/tai-video-web/jobs/{job_id}`
- `GET /api/tai-video-web/jobs/{job_id}/file` — tải file kết quả (mp4 hoặc mp3).
- `POST /api/tai-video-web/jobs/{job_id}/cancel`

## 5. Output
- Video: sao chép vào `data/tai_video_web/output/`, đồng thời đưa thẳng vào `VideoWorkspace`
  (`chinh_sua_video`) để mở ngay trong khung editor lớn — **không có ô preview nhỏ riêng trong
  sidebar**, video đang phát trong khung lớn CHÍNH LÀ kết quả.
- Audio-only: chỉ lưu vào `data/tai_video_web/output/`, KHÔNG đưa vào editor (không có gì để phát
  trong khung video) — sidebar hiện 1 nút tải file MP3 (không phải "preview", là bàn giao kết quả
  duy nhất có thể cho audio).

## 6. UI — tiến trình hiện ở đâu
`S.updateBusyProgress()` — cùng cơ chế overlay `#busy` mà mọi module AI khác dùng, nằm bên trong
`#stage` (khung video lớn ở giữa), không phải trong sidebar. Panel sidebar (`#panel-taivideoweb`)
chỉ có: URL, chất lượng, video/audio-only, nút tải, thanh tiến trình cục bộ (đồng bộ với overlay).

## 7. Kết quả test thật (đã chạy, không phải mô phỏng)
URL test: `https://www.youtube.com/watch?v=jNQXAC9IVRw` ("Me at the zoo" — video YouTube công khai
đầu tiên, ổn định, ~19s, hay dùng để test yt-dlp).
- **quality=360p, video**: tải thành công, `probe_video()` xác nhận file hợp lệ: 320×240, 15fps,
  19.014s, có audio. Đưa vào `VideoWorkspace.create()` thành công, session_id thật tạo ra được.
  `WebVideoJobManager.start()` chạy đầy đủ qua `status="done"` với `result.editor` đúng shape mà
  `applyInfo()` phía frontend cần.
- **audio_only=True**: tải thành công, xuất ra file `.mp3` thật (457,388 bytes) qua
  yt-dlp `FFmpegExtractAudio` postprocessor.
- Cả 2 lần đều KHÔNG có audio/video tách stream cần merge thủ công (source đã là 1 file), nhưng
  logic `merge_output_format`/remux-MP4 dùng chung code path đã test ở `app.modules.tai_video`
  (Facebook) nên rủi ro thấp cho các video HD cần ghép thật.

## 8. Khi lỗi cần gửi
```
app/modules/tai_video_web/
web/modules/tai_video_web/
```
Không cần gửi `tai_video/` (Facebook) nếu lỗi không liên quan — 2 module độc lập hoàn toàn, không
dùng chung downloader/job manager.

## 9. Giới hạn đã biết
- Chưa test thật với video 1080p/HD cần merge video+audio tách stream thật sự (video test dùng để
  kiểm tra rất ngắn/thấp độ phân giải nên yt-dlp trả về 1 file duy nhất luôn) — code path merge
  giống hệt module Facebook đã dùng thật trong production, rủi ro thấp nhưng chưa có bằng chứng
  test thật riêng cho trường hợp merge.
- Không kiểm duyệt nội dung/bản quyền — giống mọi downloader khác trong dự án, chỉ nên dùng với
  nội dung công khai / có quyền tải.
