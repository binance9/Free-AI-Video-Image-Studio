# AI Video Factory 0.8 · FREE LOCAL EDITION

Bản này giữ nguyên khung editor đã chốt nhưng **loại bỏ toàn bộ phụ thuộc bắt buộc vào API trả phí**. Editor cơ bản chạy local ngay; các tính năng AI dùng model open-source/local tải miễn phí lần đầu rồi lưu trên máy.

## Chạy trên Windows

1. Giải nén ZIP vào thư mục mới.
2. Double-click `START_VIDEO_FACTORY.bat`.
3. App tự mở trình duyệt ở một cổng trống.
4. Khi cần **Phụ đề AI / Dịch / AI Ảnh**, bấm `⚙ AI LOCAL > CÀI BỘ AI LOCAL MIỄN PHÍ`, hoặc chạy `SETUP_FREE_AI.bat` một lần.

## Nguyên tắc miễn phí

- Không cần OpenAI API key.
- Không cần Jamendo Client ID.
- Không có phí theo token, ảnh, video hay số lượt.
- Model AI không đóng gói trong ZIP vì dung lượng lớn; lần đầu dùng sẽ tải miễn phí từ nguồn model về `data/models/`.
- Sau khi model đã tải, các lần dùng sau chạy từ máy. Dịch một cặp ngôn ngữ mới có thể cần tải thêm gói Argos miễn phí.

## Tính năng

### Video Editor
- Tải video + preview.
- Cắt / ghép đầu-cuối / hoàn tác.
- Chèn chữ, ảnh, GIF, sticker.
- Kéo, resize, xoay, opacity, timing, layer order.
- Render MP4 bằng FFmpeg.

### Văn bản / Karaoke
- Nhiều mẫu caption, meme, gaming, cinematic, karaoke.
- Font, màu chữ, viền, nền, bóng.
- Lời bài hát: dùng lời tự viết hoặc nội dung bạn có quyền sử dụng; app không tự lấy nguyên lời bài hát có bản quyền từ Internet.

### Phụ đề AI local
- `faster-whisper` chạy trên máy.
- Tự nhận ngôn ngữ và tạo timing.
- Model mặc định: Whisper `small` để cân bằng độ chính xác / tài nguyên.

### Dịch phụ đề local
- Argos Translate chạy local.
- Việt / Anh / Nhật / Hàn / Trung / Thái / Tây Ban Nha / Pháp.
- Nếu chưa có model của cặp ngôn ngữ, app tự tải gói miễn phí lần đầu.

### AI Ảnh local
- Stable Diffusion v1.5 qua Diffusers.
- Tạo ảnh từ mô tả và sửa từ ảnh tham chiếu (img2img).
- Preset ảnh thật / hoạt hình 3D / anime / cinematic / minh họa / sản phẩm / fantasy.
- Sinh ở kích thước nhẹ rồi upscale local lên 1K/2K/4K để phù hợp video.
- Không cần API key. Model khá lớn nên lần đầu tải có thể mất thời gian.

### Nhạc local
- Có 5 loop khởi đầu do project tạo, không lấy từ bài hát thương mại.
- Tải MP3/WAV/M4A/AAC/OGG/FLAC của bạn lên; file được thêm vào kho local.
- Tìm/gợi ý theo mô tả và tag trong kho local.
- Tự chọn đoạn nổi bật bằng phân tích năng lượng, chỉnh volume và giữ/bỏ tiếng gốc.
- App không tự tải trái phép các bài hát thương mại phổ biến trên nền tảng khác.

### Sticker / GIF
- 30 sticker local có sẵn + tải sticker/GIF riêng.
- GIPHY vẫn là tiện ích **tùy chọn**; editor không phụ thuộc vào nó. Nếu dùng GIPHY, key developer của GIPHY được lưu trong trình duyệt và không liên quan API trả phí của Studio.

## Dung lượng / hiệu năng

`SETUP_FREE_AI.bat` cài PyTorch, Diffusers, Faster-Whisper và Argos. Các package/model có thể chiếm vài GB. AI Ảnh chạy nhanh hơn nhiều khi máy có GPU; CPU vẫn có thể chạy nhưng chậm.

## Cấu trúc module

- `app/modules/video_editor/` — cắt/ghép/render/overlay.
- `app/modules/subtitle_local/` — Whisper local.
- `app/modules/translate_local/` — Argos Translate.
- `app/modules/image_ai_local/` — Stable Diffusion local + upscale.
- `app/modules/music_local/` — kho nhạc local + chọn đoạn + mix.
- `app/modules/text_templates/` — mẫu chữ.
- `web/js/` — frontend chia theo chức năng.

## Internet dùng khi nào?

- Lần đầu cài package AI local.
- Lần đầu tải Whisper / Stable Diffusion / gói dịch Argos.
- GIPHY nếu bạn tự bật tiện ích đó.

Không có dịch vụ AI trả phí bắt buộc.


## AI 3D LOCAL

Module `model_3d_local/` được tách hoàn toàn khỏi AI ảnh và video editor. Backend mặc định là TripoSR: ảnh → GLB, có thể render preview quay 360°. Prompt → 3D dùng AI ảnh local tạo concept trước rồi chuyển sang backend 3D. Cài riêng bằng `SETUP_FREE_3D.bat` để người không dùng 3D không phải cài dependency nặng. Hunyuan3D được chừa adapter riêng cho nâng cấp máy mạnh sau này.

### Video Cleanup 0.8.7.8
- Xóa nền video AI local: người/nhân vật hoặc vật thể tổng quát; WebM trong suốt hoặc MP4 nền màu.
- Xóa chữ/icon/logo cố định: vẽ vùng trực tiếp trên preview; FFmpeg nhanh hoặc OpenCV inpaint.
- Lần đầu dùng AI cleanup: chạy `SETUP_VIDEO_CLEANUP_AI.bat`.


### Emoji kiểu khung chat 0.8.7.8
- Tab Emoji là mặc định trong mục Emoji & Nhãn dán.
- Có tìm kiếm, danh mục và lịch sử gần đây.
- Bấm emoji sẽ chuyển emoji thành PNG trong suốt bằng Canvas của trình duyệt rồi dùng pipeline sticker hiện có để preview/render.
- Sticker local và GIPHY vẫn là module/tab riêng.
