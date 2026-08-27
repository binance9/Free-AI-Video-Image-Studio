"""Focused exceptions for video editing failures."""


class VideoEditorError(RuntimeError):
    """Base error raised by the video editor."""


class FFmpegNotFoundError(VideoEditorError):
    """Raised when ffmpeg or ffprobe cannot be located."""


class InvalidVideoRequest(VideoEditorError, ValueError):
    """Raised when a cut or merge request is invalid."""
