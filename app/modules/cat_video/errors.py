"""Focused exceptions for the standalone video-cut module.

Deliberately NOT shared with app.modules.chinh_sua_video.errors - this module
is meant to be fully independent (no import from chinh_sua_video), even
though the exception shapes look identical. See README_MODULE.md.
"""


class CatVideoError(RuntimeError):
    """Base error raised by the video-cut module."""


class FFmpegNotFoundError(CatVideoError):
    """Raised when ffmpeg or ffprobe cannot be located."""


class InvalidVideoRequest(CatVideoError, ValueError):
    """Raised when a cut request is invalid."""
