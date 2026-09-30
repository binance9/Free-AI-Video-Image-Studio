AI VIDEO DIRECTOR V6 - QUALITY FIRST

MUC TIEU:
- Uu tien chat luong nhan vat va video.
- Character Lock xuyen canh bang Character Anchor + img2img/edit neu tao_anh_ai ho tro.
- Image technical QA + Video technical QA.
- Repair chi scene bi fail, retry co gioi han.
- High/Final master huong toi 1080p, Lanczos + sharpen nhe + encode chat luong cao.
- Khong fake semantic face/identity score neu bot chua co vision evaluator.

CAI DAT:
1. Giai nen ZIP vao thu muc goc ai_video_factory.
2. Chay INSTALL_AI_VIDEO_DIRECTOR_V6.bat.
3. Tat bot hoan toan va mo lai.
4. Ctrl+F5 trinh duyet.
5. GET /api/ai-video-director/status phai co build = v6-seedance-prompt-contract.

TEST DE NGHI:
- Tao clip 10-15 giay, bat Character Lock, quality = FINAL.
- Kiem tra data/ai_video_director/productions/.../production_manifest.json.
- FINAL_VIDEO.mp4 chi duoc danh dau done sau khi Final QA PASS.

Luu y:
- 1080p final master la upscale/render target, khong the tao chi tiet that neu model video goc qua mo.
- Character identity tot hon nho anchor/reference, nhung semantic identity 100% van can model/reference/vision QA phu hop.

V6 PROMPT CONTRACT: CHU DE/CAM XUC -> HINH ANH -> CAMERA -> PHONG CACH -> SHOT ACTION+SOUND.
Nhan vat nhat quan; hanh dong thi hien tai; moi shot ket thuc Cut; toi da 4-6 shot cho video ngan khi co the.


V6.1 FIX: UI label FINAL Quality First maps request quality to high. Backend contract remains draft/balanced/high compatible.


V6.2 SPEED + ETA:
- Live ETA + elapsed time in AUTO PRODUCE progress.
- CPU voice/music prep runs parallel with GPU generation.
- HIGH mode skips redundant second 1080p encode after normalized scenes, saving time and avoiding generation loss.
- NVENC HIGH uses p5 CQ18 for faster finishing while preserving quality.
