V9 FAST DOWNLOAD PATCH

Mục đích
- Tận dụng phần SDXL đã tải trước đó.
- Resume từ Hugging Face cache, không cố tải lại từ đầu.
- Dùng hf-xet (backend tải hiện tại của Hugging Face).
- Tăng concurrency ở mức vừa phải.
- Tách download khỏi Swagger warmup.

Cách dùng
1. Tắt cửa sổ download/warmup cũ.
2. Giải nén patch vào thư mục gốc ai_video_factory.
3. Cho phép Replace file SETUP_CHARACTER_2D_SDXL.bat.
4. Chạy SETUP_CHARACTER_2D_SDXL.bat.
5. Khi báo [OK], chạy RUN_CHARACTER_2D_ADDON.bat.
6. Trong /docs: GET /character-2d/engine -> POST /character-2d/engine/warmup -> POST /character-2d/preview.

Nếu download bị dừng
- Chạy SETUP_CHARACTER_2D_SDXL.bat lại.
- Cache đã hoàn thành sẽ được dùng lại.
