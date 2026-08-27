from pathlib import Path

from PIL import Image

from app.modules.character_2d_addon.preserve_refine import refine_reference_image
from app.modules.character_2d_addon.service import _is_preserve_request


def test_preserve_detector_for_clean_refine():
    assert _is_preserve_request(
        'clean and refine the reference character, keep the same design, same colors, improve sharpness and detail'
    ) is True


def test_preserve_detector_does_not_steal_recolor():
    assert _is_preserve_request(
        'keep same face and proportions, change armor colors to burgundy red and gold'
    ) is False


def test_refine_reference_keeps_size_and_palette(tmp_path):
    src = tmp_path / 'src.png'
    Image.new('RGB', (256, 256), (20, 160, 70)).save(src)
    out = tmp_path / 'out.png'
    info = refine_reference_image(src, out)
    assert info['ok'] is True
    assert info['diffusion_used'] is False
    with Image.open(out) as im:
        assert im.size == (256, 256)
        r, g, b = im.getpixel((128, 128))
        assert g > r and g > b


def test_health_version_129():
    from app.api.character_2d_standalone import health
    assert health()['version'] == '1.3.1'
