FRAMEPACK — TOOL TAO VIDEO AI CHAY LOCAL 100% FREE
====================================================
Nguon chinh thuc: https://github.com/lllyasviel/FramePack
(tac gia lllyasviel - cha ControlNet; canh bao: framepack.co/.ai/.pro deu FAKE)

LAM GI:
- Sinh video DAI (toi 60 giay+) tu 1 tam anh + mo ta
- Chay hoan toan tren GPU nha (RTX 5060 Ti 16GB cua may nay la du sua)
- Khong ton tien thue AI nao

CAI DAT (chi lam 1 lan):
  Chay INSTALL_FRAMEPACK.bat
  (clone source + tao venv Python 3.10 rieng + torch cu128 cho card 50-series)

CACH DUNG (moi, gan vao khung cu):
  Chay RUN_FRAMEPACK.bat -> mo trinh duyet: http://127.0.0.1:7890
  Lan dau tien chay se TU TAI model ~35GB vao HF cache (C:\Users\BAOAN\.cache\huggingface)
  -> chi tai 1 lan, nhung lan sau mo ngay.

CACH DUNG TRONG GUI:
  1. Upload 1 tam anh (nen la anh dep, chieu ngang)
  2. Gom mo ta hanh dong muon (tieng Anh ket qua tot hon)
  3. Video se sinh tuan tu tung doan (2 giay/1 doan), xem preview duoc

VAN HANH THAT (tu test cua cong dong):
  - ~1.5-2.5 giay/frame: video 5 giay (121 frame) ≈ 5-15 phut tren 5060 Ti
  - Video cang dai chat luong giam dan → dung ngon nhat o 5-20 giay
  - Manh: anime, 1 nhan vat, camera cham. Yeu: dong vat nhieu nguoi, hanh dong nhanh

CAU TRUC TICH HOP (theo pattern tools/external nhu Hunyuan3D-2, TripoSR):
  tools/external/FramePack                        - source (da sua: model local, HF cache ngoai OneDrive)
  data/runtime_framepack/venv                     - Python 3.10 venv rieng (torch 2.11 cu128 cho card 50-series)
  INSTALL_FRAMEPACK.bat + RUN_FRAMEPACK.bat       - cai dat + chay
  app/modules/framepack + web/modules/framepack   - API + nut "FramePack Video" tren trang chu factory
  C:\Users\BAOAN\.cache\framepack_models          - 45GB model (tai bang curl 3 luong ~11MB/s;
                                                     huggingface_hub bi ket tren may nay nen khong dung)

NUT "FramePack Video" tren trang chu factory: bam la tu start server + mo GUI.
API: GET /api/framepack/status | POST /api/framepack/start | POST /api/framepack/stop

DIA CHI GUI DAT PORT 7890 (tranh dam voi tool khac dung 7860).

CAP NHAT 30/09 (BAN CHOT):
- Da BO toan bo UI rieng (card trang chu + khung iframe Gradio + file web/modules/framepack).
- FramePack gio la ENGINE AN, duoc dieu khien ngay trong form AI VIDEO DIRECTOR (khung cu):
  o cot trai co khoi "KICH BAN TIENG VIET -> VIDEO - FRAMEPACK":
    + Chi ghi kich ban tieng Viet (khong chon anh) -> AI tu dich + SDXL tu ve anh dau -> sinh video
    + Hoac chon anh cua minh + kich ban hanh dong -> dung anh do sinh video
  o Video hien ngay trong khung LIVE PRODUCTION ben phai + nut TAI VIDEO.
- Backend: app/modules/framepack (POST /api/framepack/script, GET /script-status/{job}, /video/{name}).
- Engine chay an port 7890, tu dong start khi can; sage-attention da cai (nhanh hon).
- RUN_FRAMEPACK.bat chi con la du phong (mo GUI goc cua FramePack khi can debug).
- 45GB model trong C:\Users\BAOAN\.cache\framepack_models LA NAO CUA ENGINE — KHONG duoc xoa.
