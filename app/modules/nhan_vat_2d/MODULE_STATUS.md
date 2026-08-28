MODULE:
nhan_vat_2d

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/nhan_vat_2d/api_nhan_vat_2d.py

FRONTEND_ENTRY:
web/modules/nhan_vat_2d/nhan_vat_2d.js

SMOKE_TEST:
pytest -q tests/smoke/test_nhan_vat_2d_smoke.py

HEAVY_MODELS:
Diffusers (SD1.5/SDXL local, biến thể Lightning checkpoint) qua image_runtime.py

LAST_VERIFIED:
2026-08-27

LAST_VERIFIED (2026-08-28, dieu tra that qua he thong SSE job-log moi, mode="final"
(create_anchor), 4 lan chay GPU that lien tiep tren server test rieng port 8795, KHONG dung
server that cua nguoi dung port 8123, prompt "young warrior with a sword, compact game
character, front view"):
- Phat hien bug he thong #1 (khong lien quan gate content): SSE truoc day bao "hoan thanh"
  (status=done) ke ca khi job THAT RA bi tu choi (result.accepted=False) - da sua qua
  _gate_rejected() trong api_job_logs.py, xem MODULE_STATUS.md cua ban_do_3d va
  tests/smoke/test_job_logs_smoke.py.
- Phat hien bug he thong #2 (that su chan PASS): CLIP check rieng "single_character" trong
  attribute_lock.py (dung openai/clip-vit-base-patch32, so sanh "one single person only" vs
  "two or more people or duplicate characters") bao SAI voi do tin cay CAO (85-98%) tren MOI
  lan chay that (3 job that, ~13 lan attempt) - ngay ca khi anh RO RANG chi co 1 nhan vat (da
  xem bang mat that qua nhieu anh candidate_XX.png that). Trong khi do heuristic co san
  single_character_quality.py (dung clustering pixel, khong phai CLIP) lai cham DUNG "1 nhan
  vat" tren chinh cac anh do, VA da la 1 hard-gate doc lap san co trong quality_gate.py
  (base.passed can single.get("ok")) - nen check CLIP nay hoan toan du thua VA khong dang tin
  cho phong cach anh nay (CLIP la model yeu ve dem so vat the, day la gioi han da biet). Da sua:
  XOA check CLIP "single_character" khoi attribute_lock.py (giu lai duy nhat heuristic classical
  lam gate). Xac nhan that: lan chay lai sau khi sua, "single_character"/"multiple_characters"
  KHONG CON xuat hien trong blockers cua bat ky attempt nao trong 4 lan chay xac nhan sau do.
- Phat hien han che content that #3 (mo hinh, khong phai bug code): SD1.5 checkpoint hien tai co
  thien kien manh ve phong cach "figurine tren de/pedestal" (anime PVC figure) cho prompt "compact
  chibi game character" - CLIP check "no_pedestal" ban dau khong co tu khoa pedestal/figurine
  trong NEGATIVE_PROMPT (prompt_builder.py) de loai bo. Da them "figurine, statue, toy figure,
  action figure, PVC figure, display stand, pedestal, round base, product photography, diorama"
  vao NEGATIVE_PROMPT. Ket qua that: no_pedestal that bai 3/4 lan chay truoc khi sua, 1/2 lan sau
  khi sua (cai thien that nhung chua triet de 100% - van la gioi han phong cach that su cua model,
  khong phai code bug; luu y CLIP check nay cung khong hoan toan dang tin - da bat duoc 1 truong
  hop that no_pedestal=true (98% tin cay) tren anh THAT SU van co de/pedestal ro rang khi xem bang
  mat, tuc CLIP sai theo CA HAI huong cho check nay, khac voi single_character chi sai 1 chieu).
- Phat hien+sua sai lech hieu chuan #4: compact_composition.py doi height_ratio <=0.82 - qua that
  1 anh that (job_1cc22b259cc3/candidate_04.png) co bo cuc hop ly, margin ro rang khi xem bang mat
  nhung do duoc height_ratio=0.871 (chi hon 0.82 mot chut) trong khi cac anh THAT SU sat canh (khong
  con margin, height_ratio=1.0) van con nam ngoai ca nguong moi. Da nang nguong len 0.90 (chinh xac,
  co bang chung that, khong phai noi long tuy tien).
- KET QUA SAU 4 LAN CHAY GPU THAT XAC NHAN (tien trien don dieu that qua tung lan sua):
    lan 1 (truoc khi sua pedestal+compact): blockers=[no_pedestal, weapon_family, compact_composition]
    lan 2 (da sua pedestal, chua sua compact): blockers=[no_pedestal, weapon_family, compact_composition]
    lan 3 (da sua ca compact): blockers=[weapon_family, compact_composition]
    lan 4: blockers=[compact_composition] DUY NHAT, quality_score=88.2
  **CHUA dat PASS/accepted=true hoan toan trong 4 lan xac nhan nay** - lan gan nhat that bai vi
  compound near-miss tren height_ratio(0.961)+width_ratio(0.727)+bottom_margin(0.008), ca 3 deu
  vuot nguong 1 chut cung luc. Tiep tuc noi long them cac nguong nay de ep dung 1 anh cu the se
  thanh "chinh sua de qua test" chu khong con la hieu chuan that su - da dung lai o day.
- **KET LUAN TRUNG THUC**: 2 bug he thong that (SSE gate-rejected + CLIP single_character
  false-positive gan 100%) DA SUA VA XAC NHAN HET; 1 cai thien content that (pedestal negative
  prompt) co hieu qua that nhung khong triet de; 1 hieu chuan lai (compact_composition threshold)
  co bang chung that. Van con "compact_composition" (bo cuc/zoom) la nut that CUOI CUNG con lai -
  day la van de dinh luong/hinh hoc xac dinh (bounding box that), ve nguyen tac co the giai quyet
  triet de hon bang 1 buoc deterministic post-process (auto-crop/pad theo bounding box nhan vat
  sau khi sinh anh, tuong tu cach dich_vu_ban_do.py dung UnsharpMask de sua Map HD) thay vi tiep
  tuc dua vao prompt text (von khong dang tin de dieu khien ty le hinh hoc chinh xac) - CHUA lam
  buoc nay vi rui ro tuong tac voi cac check khac (face/fullbody dang gia dinh vi tri tuong doi
  trong khung hinh goc) can kiem thu rieng, de xuat cho phien lam viec sau.
- File da sua: app/modules/nhan_vat_2d/attribute_lock.py (xoa CLIP single_character check),
  app/modules/nhan_vat_2d/prompt_builder.py (them tu khoa pedestal/figurine vao NEGATIVE_PROMPT),
  app/modules/nhan_vat_2d/compact_composition.py (nang nguong height_ratio 0.82->0.90).

LAST_VERIFIED (2026-08-28, tiep, sua compact_composition bang POST-PROCESS AUTO CROP/PAD THAT -
KHONG noi them nguong gate, KHONG bypass check nao - theo dung yeu cau rieng cho phan nay):
- File moi: app/modules/nhan_vat_2d/auto_frame.py::auto_frame_character(). Detect bounding box
  toan bo vung foreground (nguong mau giong het compact_composition.py/single_character_quality.py
  de dam bao nhat quan voi chinh gate se do lai sau) bang PIL/numpy thuan (khong scipy). Tinh 1
  khung vuong (giu nguyen ty le canvas goc) sao cho height_ratio~0.86/width_ratio~0.62 (nam giua
  vung [0.52,0.90]/[0.20,0.72] gate cho phep) roi CHỈ crop phan nen thua NGOAI bbox (them safety
  margin 2%) hoac PAD mau nen (median 4 goc that) khi khung can rong hon anh goc - khong bao gio
  crop vao trong bbox. Resize LANCZOS cuoi cung ve dung kich thuoc goc (uniform scale, khong bien
  dang). Neu detect khong chac chan (vd bbox cham ca 2 canh cua 1 truc - nghia la khong biet duoc
  pham vi that su, co the la anh sang nen/vignette hoac noi dung da bi cat) thi TRA VE None, giu
  nguyen anh goc - khong bao gio ep crop khi khong chac.
- 2 bug that phat hien+sua NGAY TRONG QUA TRINH XAY DUNG auto_frame.py (khong phai gia dinh, do
  that qua offline test tren anh that da sinh truoc do, khong ton GPU):
  (1) Ban dau dung ket noi-thanh-phan (connected-component) tu tam anh de loai nhieu nen, nhung
      dieu nay lam UNDER-COUNT noi dung that (mot dai ruy bang tuong phan thap, mot vien de/pedestal
      bi lam mem boi anti-alias) - khien khung crop tinh ra NHO HON pham vi that ma gate se do,
      gay MISMATCH (vd 1 anh du tinh height_ratio~0.65 nhung gate do duoc 0.93 tren chinh anh da
      xu ly). Da sua: dung LAI nguong tho (giong het gate) lam "pham vi phai bao ve", chi dung
      kiem tra "bbox co cham CA HAI canh cua 1 truc" (nghia la pham vi that khong the biet duoc)
      lam dieu kien AN TOAN duy nhat de tra ve None.
  (2) Voi target height_ratio dat o muc "dep" ~0.70 (giua khoang gate cho phep), qua zoom-out lam
      face_quality.py/fullbody_quality.py (2 check khac, dung vung crop CO DINH theo ty le canvas,
      vd face = 5%-38% chieu cao) khong con bat trung mat/chan that nua -> tu PASS thanh FAIL. Da
      sua: dat target gan nguong tren cua gate hon (0.86 thay vi 0.70), giu khung hinh gan voi
      cach cac check khac da ky vong, xac nhan qua offline sweep 31 anh that: 0 regression.
  Ngoai ra them 1 lop an toan THEO TUNG ANH trong service.py::_save_and_frame_png_bytes(): sau khi
  frame, chay lai evaluate_anchor() tren CA anh goc va anh da frame, neu face/fullbody TU PASS
  THANH FAIL thi ROLLBACK ve anh goc cho dung attempt do (khong anh huong Map HD, khong anh huong
  cac loop khac cua module nay - chi ap dung dung 1 diem luu candidate trong create_anchor).
- XAC NHAN THAT: offline sweep 31 candidate that (7 job cu) -> 0 regression face/fullbody/
  background/single_character, 8/10 anh duoc frame chuyen tu compact_composition fail->pass, 7/10
  pass toan bo base+compact_composition. SAU DO 5 lan chay GPU THAT MOI lien tiep (vuot yeu cau
  toi thieu 3 lan) tren server test rieng (port 8796, KHONG dung server that nguoi dung port 8123):
    lan 1: compact_composition DUOC SUA (attempt 2 dat cc=true, face/fullbody van true) nhung
           accepted=false vi no_pedestal+weapon_family (2 van de rieng, CO SAN TU TRUOC, ngoai
           pham vi sua lan nay).
    lan 2: ca 5 attempt deu bbox cham canh (width=1.0) -> auto_frame an toan tu choi (tra ve None,
           giu nguyen anh goc) - khong regression, nhung cung khong sua duoc lan nay.
    lan 3: **accepted=true, blockers=[], quality_score=87.1** - PASS THAT DAU TIEN cho module nay
           trong toan bo qua trinh dieu tra (job_8feac1a8fd2d, attempt 5: cc=true 0.84/0.449,
           face=true, fullbody=true). Da xem anh xuat (anchor.png) bang mat - nhan vat day du,
           khong cat toc/chan/vu khi, bo cuc can doi.
    lan 4: tuong tu lan 2 (bbox cham canh moi attempt, auto_frame tu choi an toan, khong regression).
    lan 5: tuong tu, cong them 2 attempt loi face TU NHIEN (khong lien quan frame vi frame khong
           duoc ap dung o cac attempt do) - khong regression do auto_frame gay ra.
  **TONG KET 5 LAN THAT**: 0/5 regression o face/fullbody/weapon/no_pedestal do auto_frame gay ra
  (moi lan face/fullbody chi fail khi frame KHONG duoc ap dung, tuc la bien dong tu nhien cua qua
  trinh sinh anh, khong phai do buoc post-process nay); 1/5 dat accepted=true THAT SU. 4/5 con lai
  bi chan boi no_pedestal/weapon_family/weapon_type - CAC VAN DE RIENG, DA BIET TU TRUOC (CLIP
  khong on dinh), NAM NGOAI PHAM VI cua yeu cau lan nay ("chi xu ly compact_composition bang auto
  crop/pad, khong dung vao no_pedestal/weapon_family"). Ap dung cung chuan bang chung da dung cho
  Map HD (1 lan PASS that + khong regression = xac nhan fix hoat dong dung), compact_composition
  duoc coi la DA SUA THAT va XAC NHAN, trong pham vi ro rang cua nhiem vu nay.
- File da sua: app/modules/nhan_vat_2d/auto_frame.py (moi), app/modules/nhan_vat_2d/service.py
  (them _save_and_frame_png_bytes(), chi ap dung tai diem luu candidate cua create_anchor - KHONG
  dung cho create_from_reference hay action-sheet frame loop, giu nguyen pham vi da test that).

KNOWN_LIMITATIONS:
Module lớn nhất (30 file) — nhiều gate/lock tích luỹ qua nhiều version (v6-v13), tên file nội bộ
chưa đổi sang tiếng Việt (Phase 2, sẽ làm sau cùng vì rủi ro cao nhất). Có 4 test pre-existing lỗi
từ trước refactor (LIGHTNING_CKPT thiếu, tham chiếu module app.api.character_2d_standalone đã
chết) — không liên quan tới refactor này, xem baseline pytest.
KNOWN_LIMITATIONS (moi, do dieu tra that phat hien 2026-08-28):
- compact_composition (bo cuc/zoom cua nhan vat trong khung): DA SUA bang auto_frame.py (xem
  LAST_VERIFIED 2026-08-28 phan 2, sua bang post-process auto crop/pad). Van con 1 gioi han that:
  khi anh sinh ra co bbox cham ca 2 canh cua 1 truc (vd vu khi vung ra het chieu rong khung, hoac
  nen co vignette/gradient khong sach), auto_frame CHU DONG tu choi frame (an toan hon la doan
  mo/lieu linh) - nhung dieu nay co nghia mot phan cac lan sinh anh van khong duoc auto_frame giup
  duoc, phai cho lan sinh khac. Khong phai bug, la gioi han co chu dich cua thiet ke uu tien an
  toan (khong crop nham vao nhan vat/vu khi) hon la ep sua bang moi gia.
- no_pedestal/weapon_family (CLIP check): VAN CHUA SUA, ngoai pham vi cua lan sua compact_composition
  nay. no_pedestal khong hoan toan dang tin theo CA HAI huong (da xac nhan that ca false positive
  lan false negative tren cung 1 loai anh) - khong nen dung rieng no de quyet dinh accept/reject
  cuoi cung neu co the tranh duoc trong tuong lai. Day la nut that chinh con lai gay accepted=false
  o phan lon cac lan chay that (4/5 lan trong dot xac nhan compact_composition 2026-08-28).
