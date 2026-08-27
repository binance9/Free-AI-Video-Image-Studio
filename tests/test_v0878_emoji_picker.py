from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_version_0878():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')

def test_chat_emoji_ui():
    h=text('web/index.html')
    assert '😊 EMOJI' in h
    assert 'id="emojiSearch"' in h
    assert 'id="emojiCategories"' in h
    assert 'id="emojiGrid"' in h
    assert 'emoji_picker.js' in h
    assert '★ STICKER' in h and 'GIPHY' in h

def test_emoji_rasterizes_to_png_asset():
    js=text('web/js/emoji_picker.js')
    assert 'emojiToPng' in js
    assert 'canvas.toBlob' in js
    assert 'new File([blob]' in js
    assert "S.uploadAsset(file, 'sticker')" in js
    assert 'aivf_recent_emojis_v1' in js
    assert "['😂','cười khóc nước mắt haha lol']" in js
    assert "['😭','khóc lớn nước mắt cry']" in js

def test_emoji_css_is_compact_chat_grid():
    css=text('web/style.css')
    assert '.emoji-grid' in css
    assert 'grid-template-columns:repeat(7,1fr)' in css
    assert '.emoji-category' in css
