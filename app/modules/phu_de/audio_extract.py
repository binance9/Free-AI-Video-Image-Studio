"""Extract compact speech audio from the current video for transcription."""
from __future__ import annotations

from pathlib import Path
from app.modules.chinh_sua_video.ffmpeg_tools import run_tool


def extract_audio(video: str | Path, output: str | Path) -> Path:
    target = Path(output).resolve()
    run_tool(["-hide_banner","-loglevel","error","-y","-i",str(video),"-vn","-ac","1","-ar","16000","-c:a","libmp3lame","-b:a","32k",str(target)])
    if target.stat().st_size > 25 * 1024 * 1024:
        target.unlink(missing_ok=True)
        raise ValueError("Audio quá dài cho dịch vụ transcription hiện tại")
    return target
