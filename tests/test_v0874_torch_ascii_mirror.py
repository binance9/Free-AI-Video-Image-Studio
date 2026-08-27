from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_version_0875():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')

def test_torch_bridge_uses_mirror_not_junction():
    s = text('tools/install_character_hd_texture.py')
    assert 'def _mirror_tree_ascii' in s
    assert 'os.link(src, dst)' in s
    assert 'shutil.copy2(src, dst)' in s
    assert '[ASCII-MIRROR]' in s
    assert 'mklink /J' not in s
    assert '_create_windows_junction' not in s

def test_setup_announces_mirror():
    s = text('SETUP_CHARACTER_HD_TEXTURE.bat')
    assert '0.8.9.0' in s
    assert 'hardlink/copy mirror' in s
