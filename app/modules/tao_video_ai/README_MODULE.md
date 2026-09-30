# tao_video_ai

Module AI video độc lập cho AI Video Factory.

- TEXT_TO_VIDEO: CogVideoX-2b local
- IMAGE_TO_VIDEO: Stable Video Diffusion XT 1.1 local
- CUDA bắt buộc; tối ưu cho GPU 16 GB bằng model CPU offload
- MP4: ưu tiên NVENC (`h264_nvenc`), tự fallback `libx264`
- Progress, cancel, job status, VRAM peak metadata
- Model tải một lần từ Hugging Face rồi chạy local; đặt `AIVF_VIDEO_LOCAL_ONLY=1` để cấm tải mạng.

Bản đầu giới hạn 2-6 giây để tránh OOM và giữ trải nghiệm ổn định. Không có API trả phí.
