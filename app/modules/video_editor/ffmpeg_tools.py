"""Locate and run FFmpeg tools without shell execution."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .errors import FFmpegNotFoundError, VideoEditorError


def _resolve_binary(env_name: str, default_name: str) -> str:
    configured = os.environ.get(env_name, "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        raise FFmpegNotFoundError(f"{env_name} points to a missing file: {path}")

    found = shutil.which(default_name)
    if found:
        return found
    raise FFmpegNotFoundError(
        f"Cannot find {default_name}. Install FFmpeg or set {env_name}."
    )


def ffmpeg_bin() -> str:
    return _resolve_binary("FFMPEG_BIN", "ffmpeg")


def ffprobe_bin() -> str:
    return _resolve_binary("FFPROBE_BIN", "ffprobe")


def run_tool(args: list[str], *, tool: str = "ffmpeg") -> subprocess.CompletedProcess[str]:
    binary = ffmpeg_bin() if tool == "ffmpeg" else ffprobe_bin()
    command = [binary, *args]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown FFmpeg error").strip()
        raise VideoEditorError(f"{tool} failed ({result.returncode}): {detail}")
    return result
