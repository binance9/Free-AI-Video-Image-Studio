from pathlib import Path

from PIL import Image

from app.modules.nhan_vat_2d.output_guard import inspect_image, flatten_preview
from app.modules.nhan_vat_2d.export_gate import export_if_passed


def test_output_guard_rejects_fully_transparent(tmp_path):
    src = tmp_path / 'transparent.png'
    Image.new('RGBA', (256, 256), (0, 0, 0, 0)).save(src)
    report = inspect_image(src)
    assert report['ok'] is False
    assert report['reason'] == 'fully_transparent'


def test_output_guard_accepts_visible_character_like_image(tmp_path):
    src = tmp_path / 'visible.png'
    img = Image.new('RGBA', (256, 256), (235, 235, 235, 255))
    for x in range(70, 190):
        for y in range(30, 226):
            img.putpixel((x, y), (40, 60, 190, 255))
    img.save(src)
    report = inspect_image(src)
    assert report['ok'] is True
    assert report['visible_ratio'] > 0.2


def test_export_if_passed_flattens_to_light_background(tmp_path):
    src = tmp_path / 'alpha.png'
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    for x in range(20, 44):
        for y in range(16, 52):
            img.putpixel((x, y), (0, 120, 255, 255))
    img.save(src)

    out = export_if_passed(src, tmp_path / 'export.png', {'accepted': True})
    assert out is not None
    with Image.open(out) as im:
        assert im.mode == 'RGB'
        assert im.getpixel((1, 1)) == (235, 235, 235)
        assert im.getpixel((32, 32))[2] >= 200


def test_flatten_preview_creates_png(tmp_path):
    src = tmp_path / 'src.png'
    Image.new('RGBA', (32, 32), (255, 0, 0, 128)).save(src)
    dst = tmp_path / 'dst.png'
    flatten_preview(src, dst)
    assert Path(dst).is_file()
