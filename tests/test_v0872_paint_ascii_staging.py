from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_version_0872():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')


def test_paint_builder_has_ascii_staging():
    s = text('tools/install_character_hd_texture.py')
    assert 'def ascii_build_root()' in s
    assert 'def stage_native_source(' in s
    assert 'AIVF_NATIVE_BUILD' in s
    assert '[ASCII-STAGE]' in s
    assert 'M y t nh' in s
    assert 'stage_native_source(folder) if sys.platform.startswith("win") else folder' in s


def test_setup_keeps_toolchain_auto_detection():
    bat = text('SETUP_CHARACTER_HD_TEXTURE.bat')
    assert 'vcvarsall.bat' in bat
    assert '-vcvars_ver=14.39' in bat
    assert 'CUDA\\v12.8' in bat
