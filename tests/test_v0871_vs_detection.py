from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_bat_vs2022_detection_fix():
    bat = (ROOT / "SETUP_CHARACTER_HD_TEXTURE.bat").read_text(encoding="utf-8")
    assert "EnableDelayedExpansion" in bat
    assert 'set "VCVARS=%VSROOT%' in bat
    assert bat.find('set "VCVARS=') < bat.find('where cl >nul')
    assert "vswhere.exe" in bat
    assert "-vcvars_ver=14.39" in bat
    assert "CUDA\\v12.8" in bat

def test_version_0871():
    assert 'version: str = "0.8.9.0"' in (ROOT / "app/core/config.py").read_text(encoding="utf-8")
