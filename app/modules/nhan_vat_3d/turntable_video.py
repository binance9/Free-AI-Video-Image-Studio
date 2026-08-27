"""Transcode a browser-captured 3D turntable into an X-friendly MP4."""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin


class TurntableVideoExporter:
    def __init__(self, root: Path):
        self.root = Path(root) / "turntable_videos"
        self.root.mkdir(parents=True, exist_ok=True)

    def export(self, source_webm: Path, *, ratio: str = "1:1", duration: int = 8) -> Path:
        if ratio not in {"1:1", "16:9"}:
            raise ValueError("Tỷ lệ chỉ hỗ trợ 1:1 hoặc 16:9")
        duration = 12 if int(duration) >= 12 else 8
        width, height = (1080, 1080) if ratio == "1:1" else (1920, 1080)
        out = self.root / f"AIVF_3D_Turntable_{uuid.uuid4().hex[:8]}_{width}x{height}.mp4"
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x06101a,"
            "format=yuv420p"
        )
        cmd = [
            ffmpeg_bin(), "-y", "-i", str(source_webm),
            "-t", str(duration), "-vf", vf,
            "-r", "30", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart", str(out),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False, shell=False)
        if proc.returncode != 0 or not out.exists() or out.stat().st_size < 1024:
            detail = (proc.stderr or proc.stdout or "FFmpeg export failed").strip()
            raise RuntimeError(detail[-3000:])
        return out
