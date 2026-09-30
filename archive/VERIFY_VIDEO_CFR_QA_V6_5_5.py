from __future__ import annotations
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.ai_video_director.quality import video_quality

auto_text = (ROOT / "app/modules/ai_video_director/auto_producer.py").read_text(encoding="utf-8")
video_text = (ROOT / "app/modules/tao_video_ai/service.py").read_text(encoding="utf-8")
quality_text = (ROOT / "app/modules/ai_video_director/quality.py").read_text(encoding="utf-8")

required = {
    "auto_producer": ["normalized_cfr_30fps", "min_fps=23.5", "Chuẩn hóa CFR 30fps trước VIDEO QA"],
    "tao_video_ai": ["target_fps = 30", "effective_fps", "VIDEO_FPS_NORMALIZE_FAILED"],
    "quality": ["effective_fps", "nb_read_frames", "min_fps: float = 12.0"],
}
texts = {"auto_producer": auto_text, "tao_video_ai": video_text, "quality": quality_text}
for name, needles in required.items():
    missing = [x for x in needles if x not in texts[name]]
    if missing:
        raise SystemExit(f"VERIFY SOURCE FAIL {name}: {missing}")

ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if not ffmpeg or not ffprobe:
    raise SystemExit("VERIFY FAIL: ffmpeg/ffprobe not found")

with tempfile.TemporaryDirectory(prefix="aivf_video_cfr_verify_") as td:
    td = Path(td)
    low = td / "low8.mp4"
    cfr = td / "cfr30.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=8:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(low),
    ], check=True)
    low_qa = video_quality(low, min_width=320, min_height=180, expected_duration=3, min_fps=23.5)
    if "VIDEO_FPS_TOO_LOW" not in low_qa.issues:
        raise SystemExit(f"VERIFY FAIL: low-fps fixture was not detected: {low_qa.as_dict()}")

    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(low),
        "-vf", "fps=30", "-c:v", "libx264", "-r", "30", "-fps_mode", "cfr",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(cfr),
    ], check=True)
    cfr_qa = video_quality(cfr, min_width=320, min_height=180, expected_duration=3, min_fps=23.5)
    if not cfr_qa.passed:
        raise SystemExit(f"VERIFY FAIL: normalized CFR clip did not pass: {cfr_qa.as_dict()}")
    print("VIDEO_CFR_REAL_TEST:", cfr_qa.as_dict())

print("VIDEO_CFR_QA_V6_5_5_VERIFY: PASS")
