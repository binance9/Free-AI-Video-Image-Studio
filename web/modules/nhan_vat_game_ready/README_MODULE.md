# Frontend: Nhân vật Game Ready (web/modules/nhan_vat_game_ready)

## File chính
- `nhan_vat_game_ready.js` — toàn bộ business logic Game Ready (status Blender, tạo job, poll
  progress, hiển thị kết quả). Tách khỏi `web/modules/nhan_vat_3d/nhan_vat_3d.js` ở Phase 1.5.
- `nhan_vat_game_ready.css` — style riêng cho khối `.game-ready-*` (tách khỏi `web/style.css`).

## HTML markup
Vẫn nằm vật lý trong `web/index.html`, bên trong panel `ai3d`, bọc bằng comment
`<!-- MODULE: nhan_vat_game_ready BEGIN/END -->`. Không tách ra file HTML riêng vì dự án chưa có
templating engine — thêm cơ chế đó sẽ là rewrite, ngoài phạm vi refactor này.

## Phụ thuộc (script load order trong index.html)
Phải load **sau** `web/modules/nhan_vat_3d/nhan_vat_3d.js` (đọc `window.AIVF3D.getLastAssetId()`)
và **sau** `web/modules/nhan_vat_3d/ai_3d_viewer.js` (gọi `window.AIVF3DViewer.show()`). Không
duplicate logic viewer — chỉ gọi API có sẵn.

## Namespace global
`window.AIVFGameReady = {refreshStatus}` — namespace mỏng, không tạo global rác trùng tên.

## Khi lỗi gửi
```
web/modules/nhan_vat_game_ready/
app/modules/nhan_vat_game_ready/
```
Nếu lỗi là UI không hiển thị animation sau khi Game Ready xong, gửi thêm
`web/modules/nhan_vat_3d/ai_3d_viewer.js` (viewer dùng chung, không thuộc module này).
