from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_safe_html_defaults():
    cfg = (ROOT / 'app/core/config.py').read_text(encoding='utf-8')
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    start = (ROOT / 'START_VIDEO_FACTORY.py').read_text(encoding='utf-8')
    assert 'version: str = "0.8.' in cfg
    assert 'studio=0.8.' in start
    assert 'FREE LOCAL STUDIO · 0.8.' in html
    assert 'id="ai3dPreset"' in html
    assert 'value="character_shape" selected' in html
    assert 'id="ai3dTexture" type="checkbox">' in html
    assert 'id="ai3dOptimizeMesh" type="checkbox" checked' in html
    assert '/static/js/ai_3d_presets.js?v=08' in html


def test_presets_are_isolated_and_safe():
    js = (ROOT / 'web/js/ai_3d_presets.js').read_text(encoding='utf-8')
    assert "character_shape" in js
    assert "backend: 'character_hd', texture: false, optimize: true" in js
    assert "character_color" in js
    assert js.count("backend: 'character_hd', texture: false, optimize: true") >= 2
    assert "quick_object" in js
    assert "localStorage" in js


def test_character_backend_defaults_to_shape_only():
    src = (ROOT / 'app/modules/nhan_vat_3d/character_hd_backend.py').read_text(encoding='utf-8')
    assert 'texture=False' in src


def test_direct_routes_report_actual_texture_when_available():
    src = (ROOT / 'app/modules/nhan_vat_3d/api_nhan_vat_3d.py').read_text(encoding='utf-8')
    assert 'bool(result.get("texture_applied", texture))' in src
    assert 'bool(result.get("texture_applied", payload.texture))' in src
