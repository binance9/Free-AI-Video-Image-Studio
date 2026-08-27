from pathlib import Path


def test_texture_viewer_strings_present():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "modules" / "nhan_vat_3d" / "ai_3d_viewer.js").read_text(encoding="utf-8")
    assert "FREE LOCAL STUDIO" in html
    assert "ai3dViewerMode" in html
    assert "Bake texture màu 2K" in html
    assert "textureBitmap" in js
    assert "Texture ON" in js
    assert "autoUpright" in js
