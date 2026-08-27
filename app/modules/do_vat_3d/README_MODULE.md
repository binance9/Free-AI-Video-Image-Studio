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
- `GET /api/do-vat-3d/job/{job_id}` — trạng thái job.
- `POST /api/do-vat-3d/job/{job_id}/cancel` — huỷ job (giữ nguyên `shape.glb` nếu đã có).
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

## Pipeline (tách stage đúng yêu cầu — shape không mất nếu texture lỗi)
```
INPUT (ảnh/prompt)
→ PREPROCESS (chuan_hoa_anh_do_vat, canh giữa — khác nhan_vat_3d canh lệch xuống cho "chân")
→ SHAPE (Local3DService.from_image/from_prompt, texture=False)
→ SAVE shape.glb (luôn giữ, bất kể bước sau)
→ [nếu engine = character_hd] CHUẨN HOÁ PIVOT (gọi lại mesh_finish.py — TripoSR đã tự làm rồi)
→ optional TEXTURE (Local3DService.colorize_existing trên shape.glb — lỗi thì giữ nguyên shape)
→ VALIDATE (kiem_tra_do_vat.py — thuần stdlib, KHÔNG cần trimesh/Blender)
→ DONE
```

## Cache
Model cache dùng chung `data/models/3d/` với `nhan_vat_3d` — job sau tái dùng weight đã tải, KHÔNG
tải lại. Đây là cache cấp đĩa (giống toàn bộ pipeline 3D hiện có trong dự án — mỗi lần generate là
1 subprocess mới trong venv riêng, không có tiến trình model "sống" giữa các job để giữ trong RAM).

## Low VRAM
Nếu `low_vram=true` và preset `FINAL` chọn Character-HD: tự hạ `mesh_profile` (hd→medium) và
`texture` (hd→lite), **giữ nguyên engine đã chọn** (không âm thầm đổi sang engine khác), có log rõ
lý do. `NHÁP NHANH` không bị ảnh hưởng (đã nhẹ sẵn).

## GPU lock (giới hạn — xem "Limitations")
`app.core.shared_services.heavy_gpu_job_lock()` đảm bảo tối đa 1 job đồ vật 3D nặng chạy cùng lúc
trong `do_vat_3d`. **`nhan_vat_3d` chưa được nối vào cùng lock này** (job manager đó không bị đụng
tới trong phase này để tuân thủ nguyên tắc "không rewrite Character 3D") — nghĩa là hiện tại 1 job
`nhan_vat_3d` VÀ 1 job `do_vat_3d` vẫn có thể chạy đồng thời, tranh GPU thật. Đây là giới hạn đã
biết, ghi rõ để tránh hiểu nhầm là đã có hàng đợi GPU toàn hệ thống.

## Giới hạn đã biết: poly_target chưa được enforce thật cho engine TripoSR
Test thật (xem "Kết quả test thật" bên dưới) cho thấy: `QUALITY_PRESETS[...]["poly_target_min/max"]`
hiện là **mục tiêu tham khảo**, không phải giá trị được ép cứng. Với engine `character_hd`, giá trị
này map đúng sang `mesh_profile` (hd/medium/light) và được `mesh_optimize_profiles.py` thực sự
giảm poly. Với engine `quick` (TripoSR), `Local3DService.from_image()` hiện **không forward**
`mesh_profile`/`optimize_mesh` sang `TripoSRBackend.generate()` (giới hạn có sẵn từ trước, không
phải do `do_vat_3d` gây ra) — nên triangle count là output thô của TripoSR marching-cubes, có thể
vượt xa target (ví dụ preset STANDARD ghi 15K-40K nhưng test thật ra 129,680 tam giác cho 1 viên
đá). Metadata `poly_count` LUÔN ghi số thật lấy từ `kiem_tra_do_vat.py`, không bao giờ fake theo
target. Enforce poly budget thật cho nhánh TripoSR là việc để lại cho lần sau (cần gọi thêm
`mesh_optimize_light.py`, hiện chưa làm để tránh rủi ro thay đổi hành vi mesh ngoài kế hoạch phase
này).

## Pivot / scale
Mặc định `bottom_center` cho mọi category (xem `cau_hinh_do_vat.py`). TripoSR tự chuẩn hoá pivot
bên trong `generate()` (đã có sẵn, không phải code mới); Character-HD chưa tự làm, nên
`do_vat_3d` gọi lại `mesh_finish.py` (script generic có sẵn, không duplicate) sau khi dựng shape.
`recommended_scale` là gợi ý (min/max game unit), KHÔNG ép mesh về scale tuyệt đối — chỉ lưu gợi ý
vào metadata để Map Composer sau này tham khảo.

## Kết quả test thật (đã chạy, không phải mô phỏng)
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
  liệu test tự tạo.

## Không đổi ở nhan_vat_3d/nhan_vat_2d/nhan_vat_game_ready
Toàn bộ engine TripoSR/Hunyuan3D/Blender giữ nguyên logic. Thay đổi duy nhất ở `nhan_vat_3d`:
1 tham số tuỳ chọn `vertical_bias` (mặc định giữ nguyên `0.54`) thêm vào
`image_preprocess.py::prepare_image_for_3d` để `do_vat_3d` dùng lại hàm tiền xử lý ảnh chung với
giá trị `0.5` (canh giữa, không lệch xuống như nhân vật) — 100% tương thích ngược, không ảnh hưởng
hành vi hiện tại của `nhan_vat_3d`/`nhan_vat_2d`.
