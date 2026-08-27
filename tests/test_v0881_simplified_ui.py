from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_legacy_toolrail_removed_and_home_grid_kept():
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    assert '<aside class="toolrail">' not in html
    assert 'id="homePopularTools"' in html
    assert 'data-tool-open="ai3d"' in html
    assert 'data-tool-open="bgremove"' in html
    assert 'id="previewExpandBtn"' in html

def test_preview_expand_and_version():
    js=(ROOT/'web/core/home_screen.js').read_text(encoding='utf-8')
    css=(ROOT/'web/style.css').read_text(encoding='utf-8')
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    assert 'preview-expanded' in js
    assert 'body.preview-expanded .inspector' in css
    assert '0.8.9.0' in html
