from pathlib import Path


def test_character_hd_runner_uses_cuda_fp16_and_heartbeat():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'app/modules/model_3d_local/run_character_hd.py').read_text(encoding='utf-8')
    assert 'device=device' in text
    assert 'variant="fp16"' in text
    assert '_model_load_heartbeat' in text
    assert 'torch.cuda.is_available()' in text
    assert 'num_inference_steps=50' in text
    assert 'octree_resolution=380' in text


def test_version_is_0863():
    root = Path(__file__).resolve().parents[1]
    html = (root / 'web/index.html').read_text(encoding='utf-8')
    assert '0.8.6.' in html
