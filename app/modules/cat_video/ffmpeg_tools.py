"""Locate and run FFmpeg tools without shell execution.

Own copy for this module (not imported from chinh_sua_video) so cat_video
has zero dependency on the shared editor module. See README_MODULE.md.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .errors import FFmpegNotFoundError, CatVideoError


def _resolve_binary(env_name: str, default_name: str) -> str:
    configured = os.environ.get(env_name, "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        raise FFmpegNotFoundError(f"{env_name} points to a missing file: {path}")

    found = shutil.which(default_name)
    if found and Path(found).is_file():
        return found

    # WinGet's command shim may be stale even though the real portable bundle
    # is healthy. Resolve the executable in the installed package itself.
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            package_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            executable = f"{default_name}.exe"
            try:
                candidates = sorted(
                    package_root.glob(f"Gyan.FFmpeg_*/*/bin/{executable}"),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                candidates = []
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)
    raise FFmpegNotFoundError(
        f"Cannot find {default_name}. Install FFmpeg or set {env_name}."
    )


def ffmpeg_bin() -> str:
    return _resolve_binary("FFMPEG_BIN", "ffmpeg")


def ffprobe_bin() -> str:
    configured = os.environ.get("FFPROBE_BIN", "").strip()
    if configured:
        return _resolve_binary("FFPROBE_BIN", "ffprobe")

    # Portable FFmpeg bundles keep ffprobe beside ffmpeg. This also avoids a
    # stale PATH/WinGet symlink when FFMPEG_BIN points at a healthy local bundle.
    try:
        sibling = Path(ffmpeg_bin()).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.is_file():
            return str(sibling)
    except FFmpegNotFoundError:
        pass
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
        raise CatVideoError(f"{tool} failed ({result.returncode}): {detail}")
    return result
