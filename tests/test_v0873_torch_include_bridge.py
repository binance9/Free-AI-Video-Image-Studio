from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_version_0873():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')

def test_paint_builder_has_ascii_torch_bridge():
    s = text('tools/install_character_hd_texture.py')
    assert 'def prepare_ascii_torch_bridge()' in s
    assert 'torch_include' in s
    assert 'torch_lib' in s
    assert 'os.environ["INCLUDE"]' in s
    assert 'os.environ["LIB"]' in s
    assert '[ASCII-TORCH]' in s
    assert 'torch/extension.h' in s
    assert 'prepare_ascii_torch_bridge()' in s

def test_setup_announces_torch_bridge():
    bat = text('SETUP_CHARACTER_HD_TEXTURE.bat')
    assert '0.8.9.0' in bat
    assert 'Torch hardlink/copy mirror' in bat
