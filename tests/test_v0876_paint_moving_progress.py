from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(rel): return (ROOT/rel).read_text(encoding='utf-8')

def test_version():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')

def test_paint_heartbeat_moves():
    s=text('app/modules/model_3d_local/run_character_hd_paint.py')
    assert 'def progressive_heartbeat' in s
    assert 'math.exp' in s
    assert 'args=(load_stop, 30, 58' in s
    assert 'args=(infer_stop, 65, 90' in s
    assert '% ước tính' in s
    assert 'cache {cache_gb:.2f} GB' in s
