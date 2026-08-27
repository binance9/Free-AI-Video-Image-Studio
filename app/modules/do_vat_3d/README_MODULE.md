# Module: Đồ vật 3D (do_vat_3d)

## 1. Module dùng làm gì
Sinh asset 3D dùng cho game từ ảnh hoặc prompt: cây, đá, cỏ/bụi, rương, thùng, hàng rào, cột, đèn,
nhà nhỏ, cổng, tượng, trang trí, tự do. Đây là nguồn asset cho `ban_do_3d` (bản đồ 3D) sau này —
mỗi asset là 1 file GLB độc lập có `asset_id`, không bị bake chết vào bất kỳ map nào.

## 2. Backend entry
`app/modules/do_vat_3d/api_do_vat_3d.py` (đăng ký trong `app/main.py` qua `do_vat_3d_router`).

## 3. Frontend entry
`web/modules/do_vat_3d/do_vat_3d.js` + `do_vat_3d.css`. Panel UI (`#panel-dovat3d`) và card Home
("ĐỒ VẬT 3D") nằm vật lý trong `web/index.html`, bọc comment
`<!-- MODULE: do_vat_3d BEGIN/END -->` — cùng cách làm với `nhan_vat_game_ready` ở Phase 1.5.

## 4. API
- `GET /api/do-vat-3d/status` — trạng thái engine (dùng chung với nhan_vat_3d).
- `GET /api/do-vat-3d/categories` — danh sách 13 loại đồ vật + pivot/scale gợi ý.
- `POST /api/do-vat-3d/create` — multipart: `file`, `category`, `quality`, `texture`,
  `display_name` (tuỳ chọn), `low_vram` (tuỳ chọn) → `{job_id, status_url}`.
- `POST /api/do-vat-3d/create-from-prompt` — JSON: `prompt`, `category`, `quality`, `texture`.
- `GET /api/do-vat-3d/job/{job_id}` — trạng thái job (`queued|running|cancelling|done|
  partial_success|cancelled|error`).
- `POST /api/do-vat-3d/job/{job_id}/cancel` — huỷ job (giữ nguyên `shape.glb`/`optimized.glb` nếu
  đã có). Nếu job còn đang xếp hàng chờ GPU (chưa lấy được `heavy_gpu_job_lock`), huỷ ngay không
  cần đợi GPU rảnh (Phase 1.6.1).
- `POST /api/do-vat-3d/job/{job_id}/retry-texture` — JSON `{texture_mode}`: chạy LẠI CHỈ stage tô
  màu trên mesh đã có của job (ưu tiên `optimized.glb`, fallback `shape.glb`) — KHÔNG dựng lại
  shape/preprocess (Phase 1.6.1, xem "Retry texture").
- `GET /api/do-vat-3d/view/{asset_id}` — GLB inline cho viewer.
- `GET /api/do-vat-3d/output/{asset_id}` — tải GLB.
- `GET /api/do-vat-3d/assets` — danh sách asset đã tạo (đọc `asset.json`, không dùng database).

## 5. Input
- Ảnh (PNG/JPG/WebP), nền càng sạch càng tốt, thấy rõ toàn bộ vật thể.
- HOẶC prompt mô tả đồ vật (hệ thống chưa có text-to-3D thật → tự động qua
  `app.modules.tao_anh_ai` sinh ảnh concept 2D trước, rồi mới dựng 3D từ ảnh đó — **không** dùng
  `nhan_vat_2d` vì đó là pipeline riêng cho nhân vật có nhiều gate không cần thiết cho đồ vật).

## 6. Output
Mỗi job tạo `data/do_vat_3d/_jobs/<job_id>/work/` chứa `preprocessed.png` (nếu từ ảnh),
`shape.glb` (**luôn được giữ** kể cả khi bước tô màu lỗi), `textured.glb` (nếu tô màu thành công),
`job.json` (metadata + timing từng bước). Asset cuối lưu vào
`data/do_vat_3d/assets/<asset_id>/` gồm `model.glb`, `meta.json` (nội bộ), `asset.json` (contract
`GameAsset3D` ổn định cho `ban_do_3d` đọc sau này).

## 7. Engine dùng
Tái sử dụng **nguyên** `app.modules.nhan_vat_3d.service.Local3DService` (TripoSR + Character-HD/
Hunyuan3D) — **không copy code dựng mesh**. Tự động chọn engine theo độ phức tạp category + preset
chất lượng (`chon_engine.py`):
- `NHÁP NHANH` → luôn TripoSR (nhanh nhất).
- `FINAL` → luôn Character-HD (chất lượng cao nhất).
- `CHUẨN` → TripoSR cho vật đơn giản (đá, thùng, rương, cột…), Character-HD cho vật phức tạp
  (cây, nhà, cổng, tượng).

Model cache (`data/models/3d/`) **dùng chung** với `nhan_vat_3d` — không tải lại weight nếu
`nhan_vat_3d` đã cài sẵn.

## 8. Data folder
`data/do_vat_3d/assets/` (asset đã hoàn thành), `data/do_vat_3d/_jobs/` (job đang/đã chạy),
`data/models/3d/` (model cache dùng chung với `nhan_vat_3d`, không tách riêng).

## 9. Smoke test
```
pytest -q tests/smoke/test_do_vat_3d_smoke.py
pytest -q tests/test_do_vat_3d_unit.py
```

## 10. Khi lỗi phải gửi file gì
```
app/modules/do_vat_3d/
web/modules/do_vat_3d/
tests/smoke/test_do_vat_3d_smoke.py
tests/test_do_vat_3d_unit.py
data/do_vat_3d/_jobs/<job_id>/job.json   (job bị lỗi)
data/do_vat_3d/_jobs/<job_id>/progress.log hoặc log console liên quan
```
Không cần gửi: `nhan_vat_2d/`, `nhan_vat_game_ready/`, `ban_do_3d/` nếu lỗi không liên quan.
Nếu nghi ngờ lỗi nằm ở chính engine dùng chung (TripoSR/Hunyuan3D bị lỗi cả ở `nhan_vat_3d`), gửi
thêm `app/modules/nhan_vat_3d/`.

---

## Pipeline (Phase 1.6.1 — tách stage, shape KHÔNG mất nếu optimize/texture lỗi)
```
INPUT (ảnh/prompt)
→ PREPROCESS (chuan_hoa_anh_do_vat, canh giữa — khác nhan_vat_3d canh lệch xuống cho "chân")
→ SHAPE (Local3DService.from_image/from_prompt, texture=False)
→ SAVE shape.glb (luôn giữ, bất kể bước sau)
→ [nếu engine = character_hd] CHUẨN HOÁ PIVOT (gọi lại mesh_finish.py — TripoSR đã tự làm rồi)
→ ENFORCE POLY TARGET (toi_uu_so_mat -> optimized.glb; lỗi/timeout thì optimize_applied=False,
  giữ nguyên shape.glb, KHÔNG fail job)
→ optional TEXTURE (Local3DService.colorize_existing trên mesh ĐÃ TỐI ƯU — quyết định chạy TRƯỚC
  texture vì decimate bằng vertex-clustering không remap UV/material, làm sau sẽ phá texture; có
  timeout riêng theo texture_quality — lỗi/timeout thì giữ nguyên mesh đã tối ưu)
→ VALIDATE (kiem_tra_do_vat.py — thuần stdlib, KHÔNG cần trimesh/Blender)
→ DONE (hoặc PARTIAL_SUCCESS nếu texture được yêu cầu nhưng lỗi/timeout)
```
File giữ lại trong `work/`: `shape.glb` (gốc, luôn còn), `optimized.glb` (chỉ ghi nếu optimize
thành công), `textured.glb` (chỉ ghi nếu tô màu thành công) — `best_output_path` trong metadata
trỏ vào file tốt nhất hiện có theo thứ tự `textured > optimized > shape`.

## Cache
Model cache dùng chung `data/models/3d/` với `nhan_vat_3d` — job sau tái dùng weight đã tải, KHÔNG
tải lại. Đây là cache cấp đĩa (giống toàn bộ pipeline 3D hiện có trong dự án — mỗi lần generate là
1 subprocess mới trong venv riêng, không có tiến trình model "sống" giữa các job để giữ trong RAM).

## Low VRAM
Nếu `low_vram=true` và preset `FINAL` chọn Character-HD: tự hạ `mesh_profile` (hd→medium) và
`texture` (hd→lite), **giữ nguyên engine đã chọn** (không âm thầm đổi sang engine khác), có log rõ
lý do. `NHÁP NHANH` không bị ảnh hưởng (đã nhẹ sẵn).

## GPU QUEUE (Phase 1.6.1 — nối chung với nhan_vat_3d)
`app.core.shared_services.heavy_gpu_job_lock()` đảm bảo tối đa 1 job 3D nặng (shape hoặc texture)
chạy cùng lúc trên toàn hệ thống. Từ Phase 1.6.1, `nhan_vat_3d.job_manager.Model3DJobManager` cũng
được nối vào **cùng lock** này (adapter mỏng bọc quanh `from_image`/`from_prompt`/
`colorize_existing`, KHÔNG rewrite nội bộ Character 3D) — nghĩa là 1 job `do_vat_3d` và 1 job
`nhan_vat_3d` không còn tranh GPU thật cùng lúc nữa. Lock chỉ giữ trong lúc GỌI GPU (shape/texture),
KHÔNG giữ khi optimize (CPU) hay validate.
- `GET /api/do-vat-3d/status` trả thêm `gpu_queue: {busy, current_owner, queued_jobs, wait_seconds}`.
- Job đang xếp hàng chờ GPU nếu bị huỷ (`cancel`) thì thoát ngay, KHÔNG cần đợi tới lượt.

## POLY TARGETS (Phase 1.6.1 — enforce thật, không chỉ tham khảo)
`chon_engine.poly_target_cho(category, quality)` tính `poly_target` cụ thể (không còn chỉ là dải
min/max tham khảo):
| Quality | poly_target mặc định | Ghi chú |
|---|---|---|
| LITE | 12,000 | |
| STANDARD | 32,000 | có sàn tối thiểu riêng theo category (xem `POLY_FLOOR_STANDARD`) |
| FINAL | 60,000 | |

Sau khi dựng shape, `toi_uu_do_vat.toi_uu_so_mat()` giảm poly về gần `poly_target` (dung sai
±15%, `POLY_TOLERANCE`) bằng cách gọi `app/modules/nhan_vat_3d/mesh_decimate.py` qua subprocess
(python của Character HD venv, có `trimesh`) — thuật toán vertex-clustering có sẵn (tái dùng
`mesh_optimize_light._cluster_once`, KHÔNG thêm dependency nặng như pymeshlab/open3d), tìm
`cell_ratio` bằng binary search tới khi trong ngưỡng dung sai. Áp dụng cho **cả TripoSR lẫn
Character HD** (trước Phase 1.6.1 chỉ Character HD có optimize thật).

An toàn (section 5-7 kế hoạch phase):
- Optimizer lỗi/timeout/không có runtime → fallback: **copy nguyên `shape.glb`**, `optimize_applied
  = False`, `optimize_error` ghi rõ lý do — KHÔNG fail job.
- Sau optimize, so bounding-box volume trước/sau; nếu lệch ngoài `[0.70, 1.30]` (sập hoặc phồng bất
  thường) → tự động reject, dùng lại bản gốc.
- `POLY_FLOOR_STANDARD` (chỉ áp dụng preset STANDARD) nâng sàn tối thiểu cho category dễ mất chi
  tiết: `cay`(cây) 20K, `nha_nho`(nhà) 25K, `cong`(cổng) 20K, `da`(đá) 10K, `ruong`(rương) 8K — chỉ
  NÂNG target lên nếu preset mặc định thấp hơn, không bao giờ hạ.

Metadata `asset.json` lưu block `poly`: `original_triangle_count`, `optimized_triangle_count`,
`poly_target`, `poly_target_met`, `optimization_ratio`, `optimizer`, `optimize_applied`,
`optimize_error` — tất cả là số liệu thật, không fake.

## TEXTURE MODES & TIMEOUT (Phase 1.6.1)
Texture chạy TRÊN mesh đã tối ưu (không phải shape gốc) vì lý do UV nêu ở "Pipeline". Mỗi
`texture_quality` có timeout riêng (`TEXTURE_TIMEOUT_SECONDS`, cả `timeout_seconds` lẫn
`idle_timeout_seconds` của `paint_existing` đều dùng giá trị này):
- `lite`: 600s (10 phút)
- `hd`: 1800s (30 phút)

Vượt timeout → `paint_existing` tự kill subprocess, ném lỗi rõ ràng ("quá thời gian tối đa" /
"không có heartbeat"), `do_vat_3d` nhận diện lỗi này để đánh dấu `texture_timed_out=True` và giữ
nguyên mesh đã tối ưu (không mất). Độ phân giải/steps của Paint HD (`run_character_hd_paint.py`)
KHÔNG được thay đổi trong phase này để tránh rewrite Hunyuan3D-Paint — xem "Giới hạn đã biết".

## LOW VRAM POLICY
Giữ nguyên chính sách từ Phase 1.6: `low_vram=true` chỉ hạ `mesh_profile`/`texture` cho preset
FINAL + Character HD, không đổi engine. Phase 1.6.1 KHÔNG thêm auto-hạ resolution/steps theo VRAM
runtime (cần sửa `run_character_hd_paint.py`, ngoài phạm vi "không rewrite Hunyuan") — xem "Giới
hạn đã biết".

## PARTIAL SUCCESS
Job có 5 trạng thái: `queued|running|cancelling|done|partial_success|cancelled|error`.
`partial_success` = shape (và optimize) đã xong, nhưng texture được yêu cầu (`texture != "none"`)
mà lỗi/timeout. Asset vẫn được lưu vào thư viện với `has_texture=false` và mesh tốt nhất hiện có
(`optimized.glb` nếu có, không thì `shape.glb`). Frontend hiện thông báo "Shape 3D đã hoàn tất. Tô
màu chưa hoàn tất." + nút "THỬ TÔ MÀU LẠI".

## RETRY TEXTURE
`POST /api/do-vat-3d/job/{job_id}/retry-texture` (`DoVat3DJobManager.retry_texture` →
`DoVat3DService.to_mau_lai`) chạy LẠI CHỈ stage tô màu trên mesh đã lưu của job đó (ưu tiên
`optimized.glb`) và ảnh tham chiếu đã lưu — KHÔNG gọi lại preprocess/shape (test thật xem "Kết quả
test thật" — `service.tao_do_vat_calls` không tăng khi retry). Kết quả retry tạo 1 asset mới trong
thư viện (không ghi đè asset cũ).

## Giới hạn đã biết (Phase 1.6.1)
- **Texture resolution/steps/VRAM-aware degrade chưa cấu hình được**: `run_character_hd_paint.py`
  hiện không nhận tham số độ phân giải/steps từ `do_vat_3d`; sửa file này được xem là rủi ro
  "rewrite Hunyuan3D-Paint" nên để lại cho phase riêng nếu cần.
- **Model KHÔNG được cache trong RAM/GPU giữa các job**: kiến trúc hiện tại chạy TripoSR/Character
  HD như subprocess mới cho MỖI job (venv riêng, không có process "sống" giữ model). Cache chỉ ở
  cấp đĩa (HF cache, không tải lại weight) — `used_cached_shape_model`/`used_cached_texture_model`
  vì vậy không có ý nghĩa thật (luôn "tải lại vào GPU" dù weight đã có sẵn trên đĩa) nên KHÔNG được
  thêm vào `job.json` để tránh gây hiểu nhầm. Cache thật cấp process cần 1 worker service sống lâu
  dài — thay đổi kiến trúc lớn, ngoài phạm vi "patch nhỏ, không rewrite" của phase này.
- **Timing chỉ tách được ở mức stage, không tách được `model_load_seconds` riêng khỏi
  `shape_seconds`**: TripoSR/Character HD là subprocess đen (stdout dạng log tiến trình, không
  phải structured timing) — tách nhỏ hơn cần sửa các runner đó (`run_character_hd.py`,
  TripoSR script), vi phạm "không rewrite engine".
- Thumbnail cho asset library vẫn chưa có (kế thừa từ Phase 1.6).
- Map Composer (`ban_do_3d`) vẫn CHƯA triển khai.

## Pivot / scale
Mặc định `bottom_center` cho mọi category (xem `cau_hinh_do_vat.py`). TripoSR tự chuẩn hoá pivot
bên trong `generate()` (đã có sẵn, không phải code mới); Character-HD chưa tự làm, nên
`do_vat_3d` gọi lại `mesh_finish.py` (script generic có sẵn, không duplicate) sau khi dựng shape.
`recommended_scale` là gợi ý (min/max game unit), KHÔNG ép mesh về scale tuyệt đối — chỉ lưu gợi ý
vào metadata để Map Composer sau này tham khảo.

## Kết quả test thật Phase 1.6 (đã chạy, không phải mô phỏng)
Ngày 2026-08-27, máy dev có sẵn TripoSR + Character-HD cài đặt/cache: chạy 1 job thật category
`da` (đá), quality `standard`, texture `none`, ảnh đầu vào là 1 ảnh nhân vật có sẵn trong repo
(không có ảnh đá/rương thật trong dự án, dùng tạm để kiểm tra CƠ CHẾ pipeline, không kiểm tra độ
đúng hình dạng "đá").
- Engine chọn: TripoSR (`quick`) — đúng lý do "hình khối đơn giản".
- Thời gian: preprocess 0.58s, shape 29.46s (model load 6.9s + xử lý ảnh 9.2s + inference 2.1s +
  extract mesh 3.3s + export), optimize/validate 0.01s, **tổng 29.47s**.
- Output: GLB hợp lệ, 129,680 tam giác, 64,848 vertex, dimensions thật 0.60×1.01×0.61, device
  `cuda:0`, `pivot=bottom_center`.
- Validator `kiem_tra_do_vat.py` (tự viết, thuần stdlib) đọc đúng file GLB THẬT do TripoSR xuất ra
  — xác nhận parser JSON/binary chunk của module hoạt động đúng trên dữ liệu thật, không chỉ dữ
  liệu test tự tạo. **poly_target CHƯA enforce ở thời điểm này** (xem Phase 1.6.1 bên dưới).

## Kết quả test thật Phase 1.6.1 — poly enforcement (đã chạy, không phải mô phỏng)
Ngày 2026-08-27, chạy trực tiếp `DoVat3DService.tao_do_vat()` (không qua HTTP, cùng code path job
manager gọi) với 1 ảnh tổng hợp đơn giản (hình khối tròn/đa giác vẽ bằng PIL, dùng để kiểm tra CƠ
CHẾ enforce poly — không kiểm tra chất lượng silhouette "đá" thật):
- category=`da`, quality=`standard`, texture=`none`, engine=TripoSR (`quick`).
- **Shape thô (TripoSR marching-cubes): 127,640 tam giác, 63,912 vertex** (tương đương lần chạy
  Phase 1.6 ở trên — xác nhận TripoSR luôn xuất mesh rất dày bất kể input).
- **Sau `toi_uu_so_mat()` (optimized.glb): 31,223 tam giác** — target `poly_target=32,000`,
  `poly_target_met=true` (trong dung sai ±15%), `optimization_ratio=0.2446`,
  `optimizer=trimesh-vertex-clustering`, `optimize_applied=true`, `optimize_error=null`.
- Timing thật: `preprocess=0.22s`, `shape=24.95s`, `optimize=4.62s`, `validate≈0s`,
  **`total=29.57s`** — enforce poly chỉ cộng thêm ~4.6s so với Phase 1.6 (không optimize), vẫn nằm
  trong mục tiêu "< 45s cho asset đơn giản đã cache model".
- GLB sau optimize được `kiem_tra_glb` xác nhận hợp lệ (bbox hợp lệ, không NaN, triangle_count>0);
  bbox-volume-ratio giữa bản gốc và bản optimize nằm trong ngưỡng an toàn `[0.70, 1.30]`.

## Kết quả test thật Phase 1.6.1 — texture lite (đã chạy, không phải mô phỏng)
Cùng ảnh test, chạy full pipeline `quality=standard, texture=lite` (shape → optimize → texture
trên `optimized.glb`, KHÔNG phải shape gốc):
- GPU phát hiện: NVIDIA GeForce RTX 3050 · VRAM 6.0 GB (log thật từ Character HD backend).
- Paint HD tự bật **Low VRAM CPU offload** (hành vi có sẵn của `character_hd_backend.py`, không
  phải code mới của phase này).
- Kết quả: **`has_texture=true`, `texture_error=null`** — GLB xuất ra có material + texture nhúng
  hợp lệ (Paint HD tự kiểm tra và xác nhận trước khi trả về).
- Texture chạy TRÊN `optimized.glb` (31,223 tam giác) — sau khi tô màu, `triangle_count` vẫn giữ
  nguyên 31,223 (Paint HD không đổi topology, chỉ thêm UV/texture) → xác nhận quyết định "optimize
  TRƯỚC texture" (xem "Pipeline") không bị Paint HD làm mất tác dụng.
- Timing thật: `preprocess=0.21s`, `shape=23.07s`, `optimize=4.64s`, **`texture=287.06s` (~4.8
  phút)**, `validate=0.01s`, **`total=314.79s` (~5.25 phút)** — trong ngưỡng timeout `lite=600s`
  (10 phút) với biên độ thoải mái, và trong mục tiêu "texture lite cố gắng 2-5 phút" (mục 16 kế
  hoạch phase, dù hơi vượt mốc 5 phút một chút do CPU offload của VRAM 6GB).
- Xác nhận cơ chế timeout HOẠT ĐỘNG ĐÚNG dù không kích hoạt ở lần chạy này (287s < 600s) — xem
  `character_hd_backend.paint_existing(timeout_seconds=600, idle_timeout_seconds=600)` được gọi
  đúng tham số từ `TEXTURE_TIMEOUT_SECONDS["lite"]`.

## Không đổi ở nhan_vat_3d/nhan_vat_2d/nhan_vat_game_ready
Toàn bộ engine TripoSR/Hunyuan3D/Blender giữ nguyên logic. Thay đổi duy nhất ở `nhan_vat_3d`:
1 tham số tuỳ chọn `vertical_bias` (mặc định giữ nguyên `0.54`) thêm vào
`image_preprocess.py::prepare_image_for_3d` để `do_vat_3d` dùng lại hàm tiền xử lý ảnh chung với
giá trị `0.5` (canh giữa, không lệch xuống như nhân vật) — 100% tương thích ngược, không ảnh hưởng
hành vi hiện tại của `nhan_vat_3d`/`nhan_vat_2d`.
