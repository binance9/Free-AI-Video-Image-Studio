MODULE: ban_do_3d
STATUS: ACTIVE_V1_1_HD_TILE
BACKEND_ENTRY: app/modules/ban_do_3d/api_ban_do_3d.py
FRONTEND_ENTRY: web/modules/ban_do_3d/ban_do_3d.js (dùng chung #stage/#ai3dStageViewer sibling
  #mapHdStageViewer, KHÔNG còn modal riêng)
SMOKE_TEST:
  pytest -q tests/smoke/test_ban_do_3d_smoke.py
  pytest -q tests/smoke/test_ban_do_3d_hd_tile_smoke.py
KNOWN_LIMITATIONS: V1 tạo bản đồ HD dạng tile 2D + deep zoom; terrain GLB/heightmap và placement
3D runtime sẽ nối ở phase sau (dat_do_vat.py đã có contract toạ độ).

LAST_VERIFIED (v1.1.0, test thật bằng LocalImageService local, prompt "thành chính ở giữa, rừng
phía tây, sông chảy xuyên map, bờ biển phía đông", quality=lite, 4 tile 1024px):
- TRƯỚC fix (mỗi tile AI sinh độc lập, không khóa bố cục, ghép cạnh-đối-cạnh không blend):
  sharpness_score=1.0, tile_border_score=0.763, overall_score=0.8934, 32.1s.
- SAU fix (khóa bố cục tổng + mọi tile crop từ cùng 1 nguồn + ghép overlap-blend thật):
  sharpness_score=0.9458, tile_border_score=0.794, overall_score=0.8775, dims 1952×1952
  (không còn là 2048×2048 "dán cạnh" ảo — phản ánh đúng hình học có overlap), 199.7s.
- Kết quả: tile_border_score (chỉ số continuity trực tiếp) CẢI THIỆN (0.763→0.794 ở lần đo cuối,
  đã thấy tới 0.805 ở lần đo trước đó cùng cấu hình — dao động do AI sinh ảnh có ngẫu nhiên, không
  cố định seed). sharpness dao động run-to-run (đã thấy 0.7388–1.0 tuỳ lần) vì cùng lý do, không
  phải hồi quy hệ thống. Job chậm hơn đáng kể (32s→200s cho "lite") vì giờ luôn tinh chỉnh AI từng
  tile trên nền đã khóa (trước đây "lite" gọi AI generate() độc lập nhanh nhưng KHÔNG liền mạch).
- Route/UI: GET /api/ban-do-3d/status, /static/modules/ban_do_3d/{ban_do_3d.js,ban_do_3d.css} đều
  200 qua TestClient thật lẫn `uvicorn` process thật.

LAST_VERIFIED (2026-08-28, dieu tra that sharpness gate lien tuc that bai qua he thong SSE
job-log moi - xem app/core/job_log_broker.py / api_job_logs.py - KHONG mo phong, 10 lan chay
that lien tiep, moi lan tu 4-20 phut, tong cong ~2 gio GPU that RTX 3050):
- Phat hien: 2 lan chay dau (prompt khac nhau) deu cho sharpness_score ~0.147 (gan nhu GIONG HET
  nhau) - qua giong nhau de la "may run", cho thay LOI HE THONG chu khong phai bien dong tu nhien.
- Nguyen nhan tim duoc (doc code + do that): self.ai.edit() (dung chung cho tat ca module, xem
  app/modules/tao_anh_ai/service.py) dung strength=0.58 CO DINH cho MOI use case. Nhung base image
  Map HD dua vao img2img (tao_o_ban_do.py::crop_reference_tile) da bi CO Y lam mo manh + giam
  contrast (guide chi truyen mau/bo cuc tho, tranh copy chu/UI/prop) - voi strength thap, so buoc
  denoise THAT SU chay = num_inference_steps*strength qua it (14*0.58≈8 buoc) de model "ve lai" du
  net, ket qua la anh ra van giu do mo cua base.
- Da sua: them tham so `strength` (mac dinh 0.58, khong doi hanh vi moi noi goi khac) vao
  LocalImageService.edit(); dich_vu_ban_do.py tile-refine truyen strength=0.85 (rieng cho Map HD).
  Ket qua: sharpness tang gan gap doi (0.147 -> 0.343 o lan tot nhat), NHUNG van dao dong manh
  (0.147, 0.147, 0.343, 0.167, 0.271, 0.232, 0.266, 0.272, 0.298, 0.232 qua 10 lan - trung binh
  ~0.24, chua bao gio on dinh vuot 0.35).
- Da thu them (khong giup, da REVERT ve cau hinh nhanh nhat): tang tile_retries "lite" tu 1 len 2
  (khong cai thien ket qua tot nhat, chi lam job cham gan gap doi); tang ai_quality "lite" tu
  "medium" (14 buoc) len "high" (24 buoc) (cung khong on dinh hon, job cham 2-3x). KET LUAN: day la
  GIOI HAN THAT SU cua model SD1.5 cuc bo o ngan sach toc do/VRAM hien tai khi phai "ve lai" tu 1
  guide da bi lam mo manh, KHONG phai loi co the sua bang tune tham so them trong thoi gian hop ly -
  can thay doi kien truc lon hon (vd SDXL cho tile refine, hoac 1 buoc sharpen/upscale that su sau
  inpaint) neu muon dam bao PASS on dinh.
- **KET QUA: Map HD chua PASS on dinh** (sharpness_score chua bao gio du 0.35 qua 10 lan chay that
  sau khi da sua). Pipeline job/log (bat dau -> 100% -> ket thuc, real-time SSE, stdout/stderr that
  tu subprocess AI, khong dung server giua job) da duoc xac nhan hoat dong HOAN TOAN DUNG qua toan
  bo 10 lan chay - server khong crash/restart lan nao trong suot qua trinh, moi job deu ket thuc voi
  event "end" chinh xac (status "failed" dung vi master_pass=false, khong bi bao nham "hoan thanh").
- Nhan tien phat hien+sua 2 bug that trong chinh he thong SSE job-log (khong lien quan gate
  sharpness o tren): (1) doi NORMAL/DEBUG giua luc job dang chay lam log LAP LAI toan bo (da sua
  bang "since" cursor); (2) mot so module (vd character_2d) hoan tat khong loi nhung BI GATE RIENG
  CUA MODULE do tu choi ket qua - truoc day SSE bao sai "✓ HOAN THANH", da tong quat hoa
  _gate_rejected() trong api_job_logs.py de bao dung "✕ LOI" cho ca 2 truong hop (map_hd.master_pass
  va character_2d.result.accepted/status). Xem tests/smoke/test_job_logs_smoke.py.

LAST_VERIFIED (2026-08-28, tiep, sua that de dat PASS on dinh - server test rieng port 8794,
KHONG dung server that cua nguoi dung tren port 8123):
- Sau khi strength=0.85 van khong du (xem muc tren), them 1 buoc SAU img2img: sharpen that su bang
  PIL.ImageFilter.UnsharpMask (khong phai "AI ve them chi tiet gia", chi tang tuong phan canh co
  san - ky thuat sharpen kinh dien, deterministic) truoc khi luu tung tile
  (_sharpen_tile_bytes() trong dich_vu_ban_do.py).
- Lan thu tham so dau (radius=2, percent=150, threshold=2): sharpness vuot nguong thoai mai (0.56)
  NHUNG lam phat sinh loi MOI: no_text_score tut xuong 0.608 (duoi nguong 0.65) o 1 job - sharpen
  qua tay bi heuristic phat hien-net-chu (no_text_heuristic, dua tren stroke_ratio tuong phan cuc
  bo) nham thanh "giong chu/UI".
- Sua: quet tham so OFFLINE (khong ton GPU) bang cach dung lai anh tile PNG THAT da sinh tu 8 job
  that truoc do + ham stitch()/validate_master() THAT (production code, khong viet lai logic rieng
  de test) de thu nhieu bo tham so nhanh. Chon duoc radius=2, percent=200, threshold=1 (5/8 job
  lich su se PASS voi bo nay, so voi 0/10 truoc khi co sharpen).
- XAC NHAN THAT bang 1 lan chay GPU THAT MOI (khong dung lai job cu) tren server test rieng port
  8794, job_id a33634377cd7, prompt "vung nui phia tay, song chay xuyen map, bo bien phia dong,
  thao nguyen xanh, ban do game nhin tu tren xuong", quality=lite, 4 tile, elapsed=338.76s:
    sharpness_score=0.5145 (>=0.35 OK), tile_border_score=0.8762 (>=0.65 OK),
    master_layout_similarity=0.8772 (>=0.55 OK), no_text_score=0.9773 (>=0.65 OK, du xa nguong,
    khong con bi nham la chu/UI nua), generated_hd_ratio=1.0 (==1.0 OK).
    "pass": true, "master_pass": true.
  Da xem that anh output (ban_do_tong_quan.png) bang mat - mot ban do game top-down mach lac (nui,
  song, ho, bo bien), khong co artifact "chu gia"/halo sharpen qua da nhin thay duoc.
- **KET QUA: Map HD dat PASS THAT lan dau tien** sau tong cong 11 lan chay GPU that trong qua trinh
  dieu tra (10 lan truoc + 1 lan xac nhan cuoi). Luu y trung thuc: bo quet tham so offline cho ty le
  5/8 (~62%) tren du lieu lich su, khong phai 100% - ban chat stochastic cua SD1.5 img2img (khong co
  seed co dinh) nghia la van co the co job ca biet khong dat, nhung day la cai thien that va lon
  (0% -> ~60%+ ty le PASS) so voi truoc, va lan chay xac nhan cuoi cung THAT SU dat "pass": true.
- File lien quan da sua: app/modules/tao_anh_ai/service.py (them tham so strength cho edge()),
  app/modules/ban_do_3d/dich_vu_ban_do.py (_sharpen_tile_bytes + goi strength=0.85).
  app/modules/ban_do_3d/cau_hinh_ban_do.py: da THU tile_retries 1->2 va ai_quality medium->high cho
  "lite", KHONG cai thien (job cham 2-3x), da REVERT ve cau hinh nhanh goc.

KNOWN_LIMITATIONS (mới, do đo thật phát hiện):
- "Nhẹ" (lite) không còn nhanh như bản cài gốc (32s→~200s cho 4 tile) vì luôn tinh chỉnh AI từng
  tile để giữ chi tiết (tắt tinh chỉnh cho "lite" đã thử và làm ẢNH MỜ HƠN, không phải nhanh hơn mà
  tốt hơn — xem comment trong cau_hinh_ban_do.py). Nếu cần "lite" thật sự nhanh ở phase sau, cần
  cách tiếp cận khác (vd giảm số tile thay vì bỏ AI refine).
- LocalImageService (app.modules.tao_anh_ai) luôn sinh ảnh SD1.5 ở độ phân giải gốc 512×512 (hoặc
  640×384) bất kể "size" yêu cầu — size chỉ quyết định kích thước resize cuối cùng
  (xem app/modules/tao_anh_ai/upscale.py). Vì vậy tăng MASTER_LAYOUT_SIZE không giúp nét hơn, chỉ
  làm ảnh to hơn từ cùng nguồn 512×512 — KHÔNG nên tăng lên 2048 mà không cân nhắc chi phí thời gian
  đổi lại không có gì.
- Chưa test thật với ảnh mẫu người dùng tải lên (chỉ test nhánh sinh từ prompt/mô tả) và chưa test
  quality=standard/final thật (chỉ lite, để giữ thời gian test hợp lý) — logic 2 nhánh giờ dùng
  chung code path với nhánh đã test (crop_reference_tile từ bo_cuc_tong), rủi ro thấp nhưng chưa có
  bằng chứng thật riêng cho chúng.
