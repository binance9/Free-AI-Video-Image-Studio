from pathlib import Path
from app.modules.model_3d_local.windows_path_staging import has_non_ascii


def test_detects_unicode_project_path():
    assert has_non_ascii(Path(r"C:\Users\BAOAN\OneDrive\Máy tính\ai_video_factory")) is True


def test_ascii_windows_path_is_safe():
    assert has_non_ascii(Path(r"C:\Users\BAOAN\AppData\Local\AIVF3D_TMP")) is False
