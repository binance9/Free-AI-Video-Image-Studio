from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(p): return (ROOT/p).read_text(encoding='utf-8')
def test_version_0870():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')
def test_texture_bat_auto_toolchain():
    s=text('SETUP_CHARACTER_HD_TEXTURE.bat')
    for marker in ['vcvarsall.bat','-vcvars_ver=14.39','CUDA\\v12.8','DISTUTILS_USE_SDK=1','MSSdk=1','where cl','where nvcc']:
        assert marker in s
def test_texture_installer_logs_and_patches():
    s=text('tools/install_character_hd_texture.py')
    for marker in ['paint_build.log','data_ptr<long>()','data_ptr<int64_t>()','TORCH_CUDA_ARCH_LIST','clean_build','[PATCH]']:
        assert marker in s
