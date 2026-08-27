# BẢN ĐỒ HD / TILE MAP v1.1.0

Module map độc lập. V1 tập trung vào lớp thiết kế bản đồ HD dạng tile/deep-zoom để giữ nét khi phóng gần; cấu trúc manifest đã sẵn cho terrain/chunk 3D và đặt asset sau này.

- Backend entry: `api_ban_do_3d.py`
- Service: `dich_vu_ban_do.py`
- Input: prompt và/hoặc ảnh tham chiếu
- Output: `bo_cuc_tong.png` (bố cục tổng đã khóa), `map_spec.json`, `manifest_tiles.json`, tile PNG gốc, ảnh tổng quan, ảnh full (ghép có overlap-blend), validation, tọa độ đồ vật
- Quality: Nhẹ/lite, Trung bình/standard, Đẹp/final
- Nguyên tắc nét: viewer zoom theo tile gốc; ảnh tổng quan chỉ để overview, không upscale làm nguồn chi tiết
- AI: tái sử dụng `app.state.ai_image_service` nếu có; nếu AI tile lỗi với ảnh tham chiếu, giữ tile crop HD thay vì làm mất job
- Data: `data/ban_do_3d/jobs/<job_id>/`
- Khi lỗi: gửi `app/modules/ban_do_3d/`, `web/modules/ban_do_3d/`, `map_spec.json`, `manifest_tiles.json`, `validation.json`, `nhat_ky_job.json`
- V1 chưa dựng terrain GLB thực; không giả chức năng 3D terrain. Manifest/world coordinates là contract để Phase sau đặt terrain/prop/chunk.

## v1.1.0 — sửa theo yêu cầu bắt buộc (khóa bố cục + continuity + dùng viewer chính)

**Vấn đề của bản cài đặt ban đầu (v1.0.0, từ installer `CAI_DAT_BAN_DO_3D.py`):**
1. UI là 1 modal/khung nổi riêng (`#mapHdModal` + nút launcher góc màn hình), tách biệt hoàn toàn
   khỏi khung preview/viewer chính của app.
2. Không có bước "khóa bố cục tổng" — khi tạo map từ MÔ TẢ (không có ảnh mẫu), mỗi tile được AI
   sinh **độc lập hoàn toàn**, chỉ biết "hàng xóm là tile nào" qua mô tả bằng chữ trong prompt,
   không có gì đảm bảo pixel ở mép nối thật sự liền nhau.
3. `ghep_o_ban_do.py::stitch()` đặt tile **cạnh-đối-cạnh** (stride = tile_size, không trừ overlap)
   — dù tile có "overlap_px" trong metadata, con số đó không hề được dùng để chồng lấn hay blend gì
   khi ghép map full.

**Đã sửa:**
- `khoa_bo_cuc.py` (mới): tạo **MỘT** ảnh bố cục tổng duy nhất TRƯỚC khi chia tile — dùng thẳng
  ảnh mẫu nếu người dùng cung cấp, hoặc sinh 1 ảnh bằng AI theo mô tả tổng thể (khác hẳn tile) nếu
  không có ảnh mẫu. `dich_vu_ban_do.py` giờ LUÔN crop từng tile từ ảnh bố cục này (không còn nhánh
  "có ảnh mẫu" / "không có ảnh mẫu" tách biệt như trước) — tile nào cũng chia sẻ chung 1 nguồn hình
  học, không phụ thuộc AI tự "đoán" hàng xóm qua chữ nữa.
- `ghep_o_ban_do.py::stitch()`: đổi sang đặt tile **CHỒNG LẤN thật** (stride = tile_size −
  overlap_px) rồi feather-blend (gradient tuyến tính) đúng vùng chồng lấn — xóa vết AI tinh chỉnh
  riêng từng tile mà không làm méo hình. Kích thước map full giờ phản ánh đúng hình học có overlap
  (nhỏ hơn `cols × tile_size` một cách hợp lý), không phải con số cắt dán ảo trước đây.
- Frontend viết lại hoàn toàn: bỏ `#mapHdModal`/launcher nổi, dùng `#mapHdStageViewer` (sibling của
  `#ai3dStageViewer`) trong CHÍNH khung preview lớn ở giữa, sidebar `#panel-bandohd` chỉ giữ đúng 9
  control bắt buộc (ảnh mẫu, prompt, chất lượng, số tile, tiến trình, tạo map, mở map full,
  manifest, bật lưới tile). Zoom/pan bằng chuột (kéo + lăn chuột), lưới tile là overlay bật/tắt vẽ
  border + tile_id lên từng ô.
- Đặt tên tiếng Việt không dấu cho file mới (`khoa_bo_cuc.py`) và Home screen card riêng "Bản đồ
  HD" (tách khỏi card "Bản đồ 3D" placeholder cho terrain thật, vẫn giữ disabled).

Xem `MODULE_STATUS.md` cho số liệu test thật (before/after continuity score).
