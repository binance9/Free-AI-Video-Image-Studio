from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def text(p): return (ROOT/p).read_text(encoding="utf-8")

def test_home_ui_present():
    h=text("web/index.html"); c=text("web/style.css"); j=text("web/core/home_screen.js")
    assert 'homeScreen' in h and 'Tạo dự án video' in h and (('Tạo / sửa ảnh' in h) or ('Tạo dự án ảnh' in h))
    assert 'home-tool-grid' in h and 'AI 3D Studio' in h and (('Xóa chữ / Icon' in h) or ('Xóa chữ / Logo' in h) or ('Dọn video AI' in h))
    assert 'body.home-mode .home-screen' in c
    assert 'data-tool-open' in h and 'enterEditor' in j
    assert '0.8.9.0' in h and 'studio=0.8.9.0' in text("START_VIDEO_FACTORY.py")
