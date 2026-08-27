"""Public interface for AI Video Factory video editing."""

from .service import VideoEditor, cut_video, merge_videos

__all__ = ["VideoEditor", "cut_video", "merge_videos"]
