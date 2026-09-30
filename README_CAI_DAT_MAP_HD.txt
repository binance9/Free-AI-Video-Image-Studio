AI VIDEO FACTORY - BẢN ĐỒ HD TILE v1.0

CÀI AN TOÀN:
1) Tắt bot.
2) Giải nén ZIP THẲNG vào thư mục ai_video_factory.
3) Chạy CAI_DAT_BAN_DO_3D.bat đúng 1 lần.
4) Mở bot lại + Ctrl+F5.
5) Bấm nút "BẢN ĐỒ HD" ở góc dưới phải.

Tại sao phải chạy BAT một lần?
- Bản bot trên máy đã được Claude refactor mới hơn bản mà ChatGPT có.
- Installer chỉ chèn 1 router + 1 CSS + 1 JS vào đúng project hiện tại, có backup trước khi sửa.
- Không ghi đè app/main.py hoặc web/index.html bằng file cũ.

V1 LÀM THẬT:
- Prompt +/hoặc ảnh mẫu -> MapSpec.
- Nhẹ / Trung bình / Đẹp.
- Chia 4/6/8/10/12/16/20 tile.
- Từng tile có context hàng xóm.
- Từng tile là ảnh gốc riêng, không lấy overview nhỏ rồi upscale.
- Deep zoom viewer đọc từng tile gốc.
- manifest_tiles.json + map_spec.json + validation.json.
- Đo sharpness + border continuity.
- Tái sử dụng AI Image local hiện tại để refine/generate từng tile.

V1 CHƯA GIẢ VỜ LÀM:
- Chưa tạo terrain GLB/heightmap 3D thật.
- Chưa đặt prop 3D runtime; đã có toa_do_do_vat.json và world_bbox contract để nối sau.
