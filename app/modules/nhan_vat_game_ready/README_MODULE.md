# Module: Nhân vật Game Ready (nhan_vat_game_ready)

## 1. Module dùng làm gì
Hậu xử lý mesh 3D đã dựng xong (từ `nhan_vat_3d`) thành asset "game-ready": tối ưu mesh
(decimate), dựng khung xương (rig/armature), gán trọng số da (skin weights), tạo animation
placeholder (idle/run/attack_01), xuất GLB game-ready. Chạy qua Blender headless (subprocess).

## 2. Input
File GLB đã dựng xong và hợp lệ (thường là output của `nhan_vat_3d`), xác định qua `asset_id`
đang có trong `Model3DWorkspace` dùng chung.

## 3. Output
File `game_ready.glb` (đã optimize, có rig + animation `idle`/`run`/`attack_01`), kèm
`game_ready_report.json` (số bones, số tam giác trước/sau optimize).

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
```
