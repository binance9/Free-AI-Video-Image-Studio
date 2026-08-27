from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_version_0875():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')

def test_nvcc_use_cuda_workaround_in_python_runner():
    s = text('tools/install_character_hd_texture.py')
    assert 'NVCC_APPEND_FLAGS' in s
    assert '-DUSE_CUDA' in s
    assert '[WIN-CUDA]' in s

def test_nvcc_use_cuda_workaround_in_bat():
    s = text('SETUP_CHARACTER_HD_TEXTURE.bat')
    assert 'NVCC_APPEND_FLAGS' in s
    assert '-DUSE_CUDA' in s
    assert '0.8.9.0' in s

def test_keeps_ascii_staging_and_torch_mirror():
    s = text('tools/install_character_hd_texture.py')
    assert 'C2872' in s
    assert 'prepare_ascii_torch_bridge' in s
    assert 'stage_native_source' in s
    assert '[ASCII-MIRROR]' in s
