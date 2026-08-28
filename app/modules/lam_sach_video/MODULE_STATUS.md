MODULE:
lam_sach_video

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/lam_sach_video/api_lam_sach_video.py

FRONTEND_ENTRY:
web/modules/lam_sach_video/lam_sach_video.js

SMOKE_TEST:
pytest -q tests/smoke/test_lam_sach_video_smoke.py

HEAVY_MODELS:
rembg (u2net_human_seg / isnet-general-use) cho xoá nền. Xoá chữ/logo (inpaint) KHÔNG dùng model
AI/deep learning - CV cổ điển (cv2.inpaint TELEA + optical flow Lucas-Kanade), chạy bằng venv
chính (sys.executable), không cần SETUP_VIDEO_CLEANUP_AI.bat.

LAST_VERIFIED (2026-08-28, nâng cấp pipeline xoá chữ/logo - track mask + inpaint that + temporal
+ blend mep + sharpen, KHONG dung blur/mosaic - test that bang video that sinh qua FFmpeg,
khong mo phong):
- File moi: video_mask.py, video_tracking.py, video_inpaint.py, temporal_blend.py; inpaint_worker.py
  viet lai de dieu phoi ca pipeline, giu nguyen CLI cu, them --feather.
- API moi: POST /api/cleanup/preview/{session_id} (xem truoc that 1 frame: goc->mask->inpaint->
  final, dong bo, <1s). API cu /overlay them truong feather (0-10, mac dinh 6).
- Test that (video FFmpeg gradients + drawbox logo, KHONG mo phong):
  Laplacian variance vung xoa = 31.0 vs baseline "chi blur" = 5.8 (net hon ~5x).
  Ty le pixel den/trang thuan (dau hieu logo) giam 80.2% -> 0%.
  Quan sat anh: vung xoa la mang mau lien tuc hoa nen, KHONG con bong mo hinh hop nhu blur.
  Test tracking xac dinh (khong ngau nhien): pan 3,2 px/frame x10 frame -> bam dung sai so <=2px;
  zoom 1.03x/frame x7 frame (tong 1.23x) -> bbox phinh dung ty le 1.233x.
- 11/11 test trong tests/smoke/test_lam_sach_video_smoke.py PASS (gom 1 test end-to-end chay that
  inpaint_worker.py qua subprocess that, 2 test goi API preview/overlay that qua TestClient).
- Da phat hien va sua 1 bug that trong luc test: Windows Popen(text=True) mac dinh decode theo
  codepage he thong (cp1252) - worker in tieng Viet qua stdout gay UnicodeDecodeError o phia doc
  (job_manager.py). Sua bang cach ep ca 2 phia dung encoding="utf-8" (sys.stdout.reconfigure trong
  worker + Popen(..., encoding="utf-8") trong job_manager.py).

KNOWN_LIMITATIONS:
- Xoa nen (background_worker.py) van can rembg/onnxruntime, cai rieng qua
  SETUP_VIDEO_CLEANUP_AI.bat, khong dung chung venv voi Character HD.
- cv2.inpaint (khong phai loi tracking) co the de lai 1 vet toi nho o goc mask tren noi dung hinh
  hoc cuc doan, nen mau phang tuyet doi giap nhau truc tiep (vd SMPTE color-bar test pattern) - da
  co lap va xac nhan day la gioi han von co cua thuat toan Fast-Marching, khong xuat hien voi video
  that co texture/gradient tu nhien (xem README_MODULE.md muc 9b).
- Khong dung tracker CSRT/KCF (can opencv-contrib, khong co trong venv) - dung Lucas-Kanade optical
  flow, da test that voi pan/zoom mo phong co kiem soat, chua test voi video pan/zoom quay that.
- Preview la 1 frame tuc thi (dong bo, <1s), khong phai stream lien tuc toan bo video theo frame.
