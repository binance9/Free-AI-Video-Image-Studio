AI VIDEO DIRECTOR STUDIO V2 - AUTO PRODUCE
==========================================

CAI DAT
1. Giai nen ZIP THANG vao thu muc goc ai_video_factory (noi co app/, web/, START_VIDEO_FACTORY.py).
2. Chay INSTALL_AI_VIDEO_DIRECTOR.bat.
3. Tat bot va mo lai.
4. Bam nut: AI DIRECTOR.

QUY TRINH CHO NGUOI MOI
1. Go 1 cau y tuong.
2. Bam "LEN KICH BAN + STORYBOARD".
3. Xem/sua tung scene neu muon.
4. Bam "AUTO PRODUCE VIDEO".
5. Director tu dieu phoi:
   tao_anh_ai -> tao_video_ai -> voice local Windows neu co -> subtitles.srt -> nhac local neu co -> FFmpeg -> FINAL_VIDEO.mp4.
6. Bam tai FINAL_VIDEO.mp4 khi job hoan tat.

CAC FILE DUOC LUU TRONG data/ai_video_director/productions/<job>/
- project.json
- scenes/scene_XX.png
- scenes/scene_XX_raw.mp4
- scenes/scene_XX_final.mp4
- subtitles.srt
- voice_mix.wav (neu Windows SAPI hoat dong)
- visual_master.mp4
- production_manifest.json
- FINAL_VIDEO.mp4

NGUYEN TAC
- Director la lop dieu phoi, KHONG gop logic cac module cu.
- tao_anh_ai van tu phu trach anh.
- tao_video_ai van tu phu trach AI video.
- am_nhac van la thu vien nhac local; Director chi tim 1 track phu hop neu co.
- Neu voice/nhac chua kha dung, video van xuat; manifest ghi warning that, khong fake PASS.
- Caption luon co file SRT theo timeline storyboard.
- AUTO PRODUCE hien toi uu cho 15-90 giay; moi scene khoang 5 giay de phu hop video backend local 2-6 giay.

GPU
- RTX 5060 Ti 16GB duoc nham toi.
- Chi mot pipeline video lon duoc giu tren GPU tai mot thoi diem boi tao_video_ai.
- Video normalize/final encode uu tien h264_nvenc neu FFmpeg co NVENC, fallback libx264 neu khong co.

MODEL
- Model video khong nam trong ZIP vi co the nang nhieu GB.
- Lan dau co the can download model neu cache chua co va AIVF_VIDEO_LOCAL_ONLY != 1.
