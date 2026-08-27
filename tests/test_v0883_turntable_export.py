from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_turntable_backend_and_ui():
    api=(ROOT/'app/modules/nhan_vat_3d/api_nhan_vat_3d.py').read_text(encoding='utf-8')
    mod=(ROOT/'app/modules/nhan_vat_3d/turntable_video.py').read_text(encoding='utf-8')
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    js=(ROOT/'web/js/ai_3d.js').read_text(encoding='utf-8')
    viewer=(ROOT/'web/js/ai_3d_viewer.js').read_text(encoding='utf-8')
    assert '@router.post("/turntable")' in api
    assert 'libx264' in mod and '1920, 1080' in mod and '1080, 1080' in mod
    assert 'ai3dTurntableExport' in html and 'LƯU MP4' in html
    assert 'captureTurntable' in viewer and 'captureStream' in viewer
    assert "fetch('/api/3d/turntable'" in js

def test_version_0883():
    assert '0.8.9.0' in (ROOT/'app/core/config.py').read_text(encoding='utf-8')
