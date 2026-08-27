from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_viewer_is_separate_module():
    js = ROOT / "web" / "js" / "ai_3d_viewer.js"
    assert js.exists()
    text = js.read_text(encoding="utf-8")
    assert "WebGL2" in text or "webgl2" in text
    assert "requestFullscreen" in text
    assert "setWire" in text
    assert "setAuto" in text

def test_viewer_ui_hooked():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="ai3dStageViewer"' in html
    assert 'id="ai3dCanvas"' in html
    assert '/static/js/ai_3d_viewer.js?v=' in html

def test_view_route_present():
    routes = (ROOT / "app" / "api" / "model_3d_routes.py").read_text(encoding="utf-8")
    assert '@router.get("/view/{asset_id}")' in routes
    assert 'media_type="model/gltf-binary"' in routes
