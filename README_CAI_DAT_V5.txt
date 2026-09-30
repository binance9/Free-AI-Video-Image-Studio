AI VIDEO DIRECTOR V5 - QUALITY FIRST

MUC TIEU:
- Uu tien chat luong nhan vat va video.
- Character Lock xuyen canh bang Character Anchor + img2img/edit neu tao_anh_ai ho tro.
- Image technical QA + Video technical QA.
- Repair chi scene bi fail, retry co gioi han.
- High/Final master huong toi 1080p, Lanczos + sharpen nhe + encode chat luong cao.
- Khong fake semantic face/identity score neu bot chua co vision evaluator.

CAI DAT:
1. Giai nen ZIP vao thu muc goc ai_video_factory.
2. Chay INSTALL_AI_VIDEO_DIRECTOR_V5.bat.
3. Tat bot hoan toan va mo lai.
4. Ctrl+F5 trinh duyet.
5. GET /api/ai-video-director/status phai co build = v5-quality-first.

TEST DE NGHI:
- Tao clip 10-15 giay, bat Character Lock, quality = FINAL.
- Kiem tra data/ai_video_director/productions/.../production_manifest.json.
- FINAL_VIDEO.mp4 chi duoc danh dau done sau khi Final QA PASS.

Luu y:
- 1080p final master la upscale/render target, khong the tao chi tiet that neu model video goc qua mo.
- Character identity tot hon nho anchor/reference, nhung semantic identity 100% van can model/reference/vision QA phu hop.
