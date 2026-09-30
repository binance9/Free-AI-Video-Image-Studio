AI VIDEO DIRECTOR V6.5.1 FPS NORMALIZE FIX

Fix:
- Normalize scene video with explicit -r 30 -fps_mode cfr before QA.
- ffprobe uses -count_frames.
- QA records avg_fps, r_fps, counted_fps, frame_count and uses robust effective FPS.
- Raw low-FPS generator clip is diagnostic only; normalized CFR clip is the QA gate.

Scope: only AI Director quality.py + auto_producer.py.
