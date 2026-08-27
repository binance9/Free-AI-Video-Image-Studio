# Module: Phụ đề (phu_de)

## 1. Chức năng
Nhận dạng giọng nói tự động (speech-to-text, local, Whisper) để tạo phụ đề từ audio của video,
kèm dịch phụ đề sang ngôn ngữ khác (local, Argos Translate). Dịch thuật được gộp vào module này
vì hiện tại chỉ được dùng cho phụ đề (không dùng cho tiêu đề/mô tả).

## 2. File chính
- `service.py` — `LocalCaptionService`: chạy faster-whisper, trả về segment có timing.
- `audio_extract.py` — `extract_audio()`: tách audio từ video bằng ffmpeg trước khi transcribe.
- `group_words.py` — gom từ thành câu/dòng phụ đề theo thời gian.
- `dich_thuat.py` — `LocalTranslationService` (trước là module `translate_local` riêng, gộp vào
  đây vì chỉ phục vụ dịch phụ đề): dịch segment bằng Argos Translate.
- `api_phu_de.py` — route API của module.
- `__init__.py` — export `extract_audio`, `LocalCaptionService`, `LocalTranslationService`.

## 3. API thuộc module
- `POST /api/editor/{session_id}/captions/transcribe`
- `POST /api/captions/translate`

## 4. Input
Video đang chỉnh sửa trong session (audio được tách ra), hoặc danh sách segment + ngôn ngữ nguồn/đích.

## 5. Output
Danh sách segment phụ đề (text + start/end time), hoặc segment đã dịch.

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.workspace.VideoWorkspace` — lấy video hiện tại của session để tách audio.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/phu_de/
web/modules/phu_de/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng, trừ khi lỗi nằm ở `chinh_sua_video/workspace.py`.

## 9. Model AI / engine sử dụng
- Whisper (faster-whisper), model mặc định `small` (xem `app/core/config.py` →
  `settings.whisper_model`), cache tại `data/models/whisper/`.
- Argos Translate (gói ngôn ngữ tải sẵn cho dịch offline).

## 10. Thư mục data/output
Không có thư mục data riêng (transcribe chạy trực tiếp trên audio tạm của session video, không
lưu lâu dài). Model cache: `data/models/whisper/`.
