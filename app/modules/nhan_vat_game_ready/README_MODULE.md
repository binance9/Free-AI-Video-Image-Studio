# Module: Nhân vật Game Ready (nhan_vat_game_ready)

## 1. Module dùng làm gì
Hậu xử lý mesh 3D đã dựng xong (từ `nhan_vat_3d`) thành asset "game-ready": tối ưu mesh
(decimate), dựng khung xương (rig/armature), gán trọng số da (skin weights), tạo animation
placeholder (idle/run/attack_01), xuất GLB game-ready. Chạy qua Blender headless (subprocess).

## 2. Input
File GLB đã dựng xong và hợp lệ (thường là output của `nhan_vat_3d`), xác định qua `asset_id`
đang có trong `Model3DWorkspace` dùng chung.

## 3. Output
Mỗi job tạo `data/nhan_vat_game_ready/jobs/<job_id>/` chứa (Phase 1.6.2 - trước đó chỉ có
`game_ready.glb` + report):
- `source.glb` — bản copy nguyên input, trước khi động vào gì.
- `optimized.glb` — sau decimate, trước khi rig (chưa có skeleton).
- `rigged.glb` — sau rig + skin bind, TRƯỚC KHI bake animation (bind pose/T-pose, dùng để cô lập
  lỗi skin khỏi lỗi animation khi debug).
- `game_ready.glb` — **FINAL, tên cố định**, có rig + skin thật + animation `idle`/`run`/`attack_01`.
- `game_ready_report.json` — Blender tự báo cáo (bones, faces trước/sau, skin_method).
- `validation.json` — kết quả **kiểm tra độc lập** (không tin báo cáo của Blender), xem mục 11.

## 4. Có Blender dependency
Có — bắt buộc Blender 4.x cài ở máy chạy backend, gọi qua `subprocess` (`blender --background
--factory-startup --python blender_game_ready.py`), không phải thư viện Python.

## 5. Blender thiếu thì status nào
`GET /api/3d/game-ready/status` luôn trả `200` (không bao giờ lỗi vì thiếu Blender):
```json
{"ok": true, "installed": false, "blender": null,
 "message": "Chưa tìm thấy Blender 4.x. Chạy SETUP_GAME_READY_3D.bat một lần.",
 "pipeline": ["optimize","rig","skin","idle","run","attack_01","export_glb"]}
```
Nút "TẠO GAME-READY GLB" trên UI khi đó sẽ báo lỗi rõ ràng thay vì tạo job, vì `service.convert()`
raise `RuntimeError` ngay khi không tìm thấy Blender.

## 6. File nào tạo skeleton
`blender_game_ready.py` — script Blender (bpy) chạy standalone qua subprocess, thực hiện toàn bộ
pipeline: import GLB → optimize mesh → **dựng rig/armature** → **auto-skin (gán trọng số da)** →
bake animation placeholder → export GLB. Đây là 1 script liền mạch (không tách nhỏ thêm — xem
mục 9 file `app/modules/nhan_vat_3d/README_MODULE.md` phần lý do không split).

## 7. File nào optimize
Cũng là `blender_game_ready.py` (bước optimize/decimate nằm ngay đầu pipeline, trước khi rig).

## 8. File nào tạo animation
Cũng là `blender_game_ready.py` (bước bake idle/run/attack_01 nằm cuối pipeline, trước export).

## 9. Frontend file nào điều khiển UI
`web/modules/nhan_vat_game_ready/nhan_vat_game_ready.js` — trạng thái Blender, nút tạo Game
Ready, poly target, progress bar, tải kết quả. **Đã tách hoàn toàn khỏi
`web/modules/nhan_vat_3d/nhan_vat_3d.js`** (Phase 1.5). Style riêng:
`web/modules/nhan_vat_game_ready/nhan_vat_game_ready.css`.

Lưu ý: HTML markup của khối Game Ready (`#ai3dGameReadyBox`) vẫn nằm **vật lý bên trong**
`web/index.html` (trong panel `ai3d`), vì dự án chưa có templating engine để tách file HTML riêng
mà không phải viết lại cơ chế render — tách phần này ra là việc ngoài phạm vi "move + rewire".
Markup được bọc bằng comment `<!-- MODULE: nhan_vat_game_ready BEGIN/END -->` để dễ định vị.

Nút điều khiển animation (Idle/Run/Attack/Stop) **KHÔNG thuộc module này** — đó là tính năng
viewer dùng chung cho mọi GLB có animation, sống trong
`web/modules/nhan_vat_3d/ai_3d_viewer.js`, tự hiện/ẩn theo `meta.animations`. Game Ready chỉ gọi
`window.AIVF3DViewer.show(url, label)` để mở kết quả trong viewer, không tự vẽ animation.

## 10. Khi lỗi cần gửi folder nào
```
app/modules/nhan_vat_game_ready/
web/modules/nhan_vat_game_ready/
```
Nếu lỗi là "không thấy animation/rig trong viewer sau khi Game Ready xong" thì có thể cần gửi
thêm `web/modules/nhan_vat_3d/ai_3d_viewer.js` (vì đó là nơi hiển thị animation, không phải nơi
tạo ra nó).

---

## Ranh giới module (sau Phase 1.5)

**`nhan_vat_3d`** chỉ chịu trách nhiệm: ảnh/prompt → shape 3D → texture/paint → GLB chuẩn →
viewer cơ bản. KHÔNG chịu trách nhiệm rig/skeleton/skinning/animation/Game Ready export.

**`nhan_vat_game_ready`** (module này) chịu trách nhiệm: GLB đã tạo → optimize → rig → skin →
animation → `game_ready.glb`.

## API (giữ nguyên, không đổi so với trước refactor)
- `GET /api/3d/game-ready/status`
- `POST /api/3d/game-ready/jobs` — body `{asset_id, target_faces}`
- `GET /api/3d/game-ready/jobs/{job_id}`

## Phụ thuộc module khác
- Nhận `asset_id` trỏ vào `Model3DWorkspace` (sở hữu bởi `nhan_vat_3d`, khởi tạo dùng chung trong
  `app/main.py`) — chỉ đọc đường dẫn file, không import logic dựng mesh của `nhan_vat_3d`.
- Frontend gọi `window.AIVF3D.getLastAssetId()` / `window.AIVF3DViewer.show()` — 2 API mỏng do
  `nhan_vat_3d` và viewer expose ra, không duplicate code.

## Lệnh test nhanh
```
pytest -q tests/smoke/test_nhan_vat_game_ready_smoke.py
pytest -q tests/test_nhan_vat_game_ready_unit.py
```

---

## 11. Phase 1.6.2 — bug thật đã tìm và sửa: "tạo xương xong nhưng nhân vật không di chuyển"

### Nguyên nhân gốc (đã xác nhận bằng GLB thật, không đoán)
`bpy.ops.object.parent_set(type="ARMATURE_AUTO")` (auto-skin của Blender, dùng thuật toán "bone
heat") **KHÔNG raise exception khi solve thất bại một phần** — nó chỉ in cảnh báo
`Bone Heat Weighting: failed to find solution for one or more bones` rồi vẫn trả về thành công.
Đây là lỗi RẤT PHỔ BIẾN với mesh AI sinh ra (TripoSR/Hunyuan) vì hình học thường không manifold/có
nhiều đảo rời rạc mà bone-heat cần mesh liền mạch để giải.

Code cũ chỉ bọc `try/except` quanh lời gọi đó — vì không có exception, code báo
`skin_method: "automatic"` (SAI) và tiếp tục export. Khi export, **Blender's glTF exporter tự phát
hiện mesh không có vertex group nào dùng được và ÂM THẦM BỎ QUA CẢ SKIN**
(`WARNING: CharacterMesh has no skin, skipping adding neutral bone data on it.`) — kết quả:
`JOINTS_0`/`WEIGHTS_0` vẫn có trong file (do code luôn khai báo attribute) nhưng **hoàn toàn không
có `skins` array nào để engine/viewer bind theo** → mesh render như static mesh dù animation clip
vẫn chạy trên node xương (chỉ là node xương không điều khiển được vertex nào của mesh).

Test thật xác nhận: chạy job Game Ready thật (trước khi sửa) trên
`data/3d_assets/8d8b1343c6f24efdabd713c1f341cdc1/model.glb` (mesh Character HD thật, 634,051 tam
giác trước optimize) → `game_ready.glb` xuất ra có `skins: null` dù mesh có đủ
`JOINTS_0`/`WEIGHTS_0`. Đối chiếu với asset đã tạo Game Ready trước đó trong thư viện: 2/3 asset
cũ cũng có `skins: []` (rỗng) — đây không phải case hiếm, mà là **thất bại phổ biến, âm thầm, đã
tồn tại từ trước**.

### Sửa gì (`blender_game_ready.py`)
- `auto_skin()` giờ **verify thật** sau khi `parent_set(type="ARMATURE_AUTO")` chạy xong: đếm % số
  vertex có tổng weight > 0.01 trên bất kỳ vertex group nào (`_weight_coverage()`). Nếu < 85%
  (`MIN_WEIGHT_COVERAGE`) — kể cả khi operator không raise gì — coi như automatic THẤT BẠI.
- Khi automatic thất bại (raise HOẶC coverage thấp): dọn sạch modifier/vertex group/parent còn sót
  lại (`_clear_skinning()`) rồi chạy fallback xác định (`_zone_fallback_weights()` — thuật toán cũ,
  gán weight theo vùng cơ thể bằng toạ độ vertex, luôn cho ra 100% coverage vì không phụ thuộc hình
  học phức tạp).
- Nếu fallback cũng không đạt 85% (gần như không thể xảy ra vì thuật toán gán REPLACE 1.0 cho mọi
  vertex) → raise thật, job FAIL rõ ràng ở stage skinning thay vì export GLB rỗng.
- `main()` giờ export thêm 3 checkpoint (`source.glb`/`optimized.glb`/`rigged.glb`) ở đúng thời
  điểm trong pipeline (xem mục 3).

### Validator độc lập mới (`validate_game_ready.py`)
Thuần stdlib (struct + json, cùng phong cách với `do_vat_3d/kiem_tra_do_vat.py`), đọc trực tiếp
`game_ready.glb` sau khi Blender export — **không tin báo cáo tự thân của Blender**:
- `skins_count`, `joints_count`, `has_joints_attr`, `has_weights_attr`.
- `weight_coverage` — đọc thật giá trị `WEIGHTS_0` (áp dụng normalize đúng theo componentType), đếm
  % vertex có tổng weight > 0.01. Đây chính là phép kiểm đã lộ ra lỗi ở trên.
- Với mỗi animation clip: `clip_keyframes` (số keyframe lớn nhất trong các channel) và
  `clip_has_motion` (đọc thật giá trị output của sampler, so 2 keyframe đầu/sau — nếu không lệch
  quá `1e-4` ở component nào thì coi là "đứng yên", KHÔNG được tính là animation hợp lệ dù tên clip
  đúng `idle`/`run`/`attack_01`).
- Kết quả: `ok` (mesh + skin dùng được — điều kiện để job không FAIL hẳn) và `animation_ok` (cả 3
  clip bắt buộc đều tồn tại VÀ có chuyển động thật — điều kiện để job được tính là Game Ready PASS
  đầy đủ, không phải chỉ `partial_success`).

`GameReady3DService.convert()` gọi validator này ngay sau export, ghi `validation.json`, và
**raise** nếu `validation.ok == False` (skin hỏng — không cho job "thành công" với 1 GLB không
skin được). Nếu skin OK nhưng `animation_ok == False`, job vẫn trả kết quả (asset vẫn lưu được,
người dùng vẫn có mesh+skin dùng được) nhưng `GameReadyJobManager` đặt status **`partial_success`**
thay vì `done` — không bao giờ báo "GAME READY PASS" giả.

### Kết quả test thật sau khi sửa (Phase 1.6.2)
Chạy lại đúng job đã fail ở trên (`data/3d_assets/8d8b1343c6f24efdabd713c1f341cdc1/model.glb`,
target_faces=45000), Blender 5.2.1 LTS thật, không mock:
- `skin_method: "zone_fallback"` (đúng như dự đoán — automatic thất bại, fallback được kích hoạt).
- `skins_count: 1`, `joints_count: 18`, **`weight_coverage: 1.0`** (100% vertex có influence).
- `animations: [idle, run, attack_01]`, `clip_keyframes: {attack_01: 30, idle: 48, run: 25}` (bake
  per-frame thật, không phải chỉ 2 keyframe tĩnh).
- `clip_has_motion`: cả 3 đều `true` → `animation_ok: true`, `validation.ok: true` → **Game Ready
  PASS thật, không giả**.
- Thời gian chạy: 11.11s (import + optimize 634K→45K tam giác + rig + skin fallback + bake 3
  animation + export 4 file GLB).

## 12. Phase 1.6.2.1 — sửa riêng RUN cycle (không đụng rig/skin/viewer)

Run cũ chỉ có 5 keyframe rời rạc, biên độ/knee-bend không được kiểm chứng số liệu, và
`validate_game_ready.py` chỉ kiểm tra "có motion" chung chung (không phân biệt được "chạy thật"
với "nhún lên xuống"). `bake_run_cycle()` (trong `blender_game_ready.py`) viết lại bằng 1 công
thức pha liên tục (`phase_l = t`, `phase_r = t+0.5 mod 1`) thay vì pose tay:
- `thigh.{L,R} = RUN_THIGH_AMP * cos(2π·phase)` → 2 chân LUÔN ngược pha chính xác (không phải "na
  ná khác nhau"), vì cùng 1 công thức lệch pha 0.5 chu kỳ.
- `shin.{L,R}` (gối) chỉ bend trong nửa chu kỳ "swing" (chân rời đất) của chính chân đó, bằng 0
  trong nửa "stance" (chân chạm đất) — tại mọi thời điểm đúng 1 chân bend, chân kia thẳng.
- `foot.{L,R}` xoay cổ chân theo pha chân đó (nhấc/đặt chân).
- `hips` hạ nhẹ (dip) đúng 2 lần/chu kỳ tại 25%/75% (lúc 2 chân đi qua vị trí giữa) + xoay rất nhẹ;
  `chest` nghiêng nhẹ cố định; `head` gần như đứng yên.
- Cycle 24 frame @ 24fps = 1.0s (đúng biên trên "0.7-1.0s" yêu cầu), frame cuối = frame đầu (loop
  liền mạch, đã verify bằng số liệu thật, xem dưới).

`validate_game_ready.py::_validate_run_gait()` (mới) đọc TRỰC TIẾP quaternion/translation thật
của clip "run" từ GLB đã export (không tin animation curve tự khai) và kiểm tra đúng yêu cầu:
- Range xoay `thigh.L`/`thigh.R` (unwrap góc quanh trục X cục bộ để tránh lỗi wrap ±180°, xem
  comment trong code — quaternion export ra có offset rest-pose lớn, phải đo RANGE chứ không đọc
  giá trị tuyệt đối).
- **Anti-phase**: hệ số tương quan Pearson giữa chuỗi góc `thigh.L(t)` và `thigh.R(t)` phải
  `<= -0.5` — nếu 2 chân cùng pha (bug y hệt điều user mô tả), correlation sẽ dương → FAIL rõ ràng,
  không chỉ "im lặng cho qua".
- Range bend gối (`shin.L`/`shin.R`), range dịch chuyển hips theo trục có biên độ lớn nhất (không
  giả định cứng trục nào là "trục thẳng đứng" sau khi glTF export đổi Z-up→Y-up).
- `run` trong `required_clips_animated` giờ **PHẢI qua được `_validate_run_gait`**, không chỉ "có
  motion nào đó" như trước — animation_ok/Game Ready PASS đầy đủ phụ thuộc đúng vào việc chạy có
  thật hay không.

### Kết quả test thật (đã chạy, không phải mô phỏng)
Cùng model Character HD thật đã dùng ở Phase 1.6.2 (`data/3d_assets/8d8b1343c6f24efdabd713c1f341cdc1/model.glb`,
634,051 tam giác), Blender 5.2.1 LTS thật, target_faces=45000, `skin_method=zone_fallback` (như
Phase 1.6.2):
- **Run duration**: 1.0s (24 frame / 24fps, frame 1→25).
- **Samples/keyframes** trong file export: 25 (per-frame, không phải chỉ 5 keyframe tác giả).
- **Rotation range thigh.L**: 1.100 rad (≈63.0°) — **Rotation range thigh.R**: 1.100 rad (≈63.0°,
  khớp thigh.L, đúng biên độ đối xứng).
- **Knee bend range** `shin.L`/`shin.R`: 0.850 rad (≈48.7°) mỗi bên.
- **Hips vertical range** (trục có biên độ lớn nhất sau export): 0.020.
- **Xác nhận left/right anti-phase**: `leg_phase_correlation = -1.0` (ngược pha hoàn hảo,
  `legs_anti_phase = true`).
- **Xác nhận loop seam**: frame 25 (t=1.0) trùng khớp frame 1 (t=0.0) tại mọi bone (do công thức
  cos/sin tuần hoàn đúng chu kỳ 1.0) — không giật ở điểm nối.
- `_validate_run_gait().ok = true`, `validation.animation_ok = true` toàn bộ — **Game Ready PASS
  thật**, không phải chỉ "có tên clip idle/run/attack_01".

Không sửa: Character 3D generator, texture, rig structure (vẫn 18 bone như cũ), `ai_3d_viewer.js`
(playback đã hoạt động từ Phase 1.6.2, không đụng vào).

**Chưa làm**: clip `walk` (mục 15 trong yêu cầu, đánh dấu optional, "ưu tiên sửa RUN chuẩn
trước") — để lại cho lần sau nếu cần, không mở rộng ngoài phạm vi "sửa run" của phase này.
Weapon-safety (mục 12) không có logic riêng theo loại vũ khí vì pipeline hiện không biết
nhân vật có cầm vũ khí gì — biên độ tay (`RUN_ARM_AMP=0.5`) được giữ thấp hơn biên độ chân
(`RUN_THIGH_AMP=0.55`) một cách thận trọng để giảm rủi ro xuyên mesh, nhưng không có kiểm tra
hình học thật.

## Giới hạn đã biết (Phase 1.6.2)
- Chưa test được trường hợp `skin_method: "automatic"` THÀNH CÔNG thật (coverage ≥85% ngay từ bone
  heat) trên máy dev này trong phase này — mesh test sẵn có đều rơi vào nhánh fallback. Logic
  nhánh "automatic" bản thân không đổi (chỉ thêm bước verify SAU khi nó chạy xong), nên rủi ro hồi
  quy thấp, nhưng chưa có bằng chứng thật cho nhánh đó ở phase này.
- Rig vẫn là 1 bộ 18 bone cố định, không thích nghi theo hình dạng nhân vật (chibi/người lớn dùng
  chung 1 tỉ lệ bone dựa trên bbox) — đúng như thiết kế "ít bone, ổn định" của bản gốc, không phải
  thứ cần sửa trong phase này.
- Chưa thêm auto-hạ/nâng poly theo VRAM hay cấu hình animation nâng cao (blend/transition giữa
  clip) — ngoài phạm vi "sửa đúng lỗi rig/skin/animation không dùng được" của phase 1.6.2.
- Không có công cụ test trình duyệt headless trong môi trường này (không Puppeteer/Playwright) —
  phần viewer (`ai_3d_viewer.js`) được xác nhận đúng bằng: `node --check` (cú pháp), static
  assertion trên source code cho các fix bắt buộc, và suy luận toán học tay (xem
  `web/modules/nhan_vat_3d/README_MODULE.md` nếu cần chi tiết) — KHÔNG phải bằng cách mở trình
  duyệt thật và nhìn nhân vật chạy. Khuyến nghị: người dùng tự mở app và bấm RUN/ATTACK trên
  `game_ready.glb` vừa tạo ở trên để xác nhận bằng mắt.
