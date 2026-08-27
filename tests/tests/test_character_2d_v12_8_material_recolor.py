from pathlib import Path
import numpy as np
from PIL import Image

from app.modules.character_2d_addon.material_recolor import recolor_materials
from app.modules.character_2d_addon.spec_parser import parse_character_spec


def _make_green_character(path: Path):
    img = Image.new('RGBA', (256, 256), (232, 232, 232, 255))
    # green garment block
    for x in range(70, 190):
        for y in range(55, 220):
            img.putpixel((x, y), (55, 145, 55, 255))
    # gold trim that should remain gold-ish
    for x in range(95, 165):
        for y in range(120, 130):
            img.putpixel((x, y), (205, 155, 35, 255))
    img.save(path)


def test_recolor_prompt_parses_red_gold_and_cape():
    spec = parse_character_spec(
        'keep same female chibi elf archer, change the armor colors to burgundy red and gold, '
        'change the cape to dark red, keep one bow and one quiver'
    )
    assert spec.armor_primary == 'red'
    assert spec.accent_color == 'gold'
    assert spec.cape_color == 'red'
    assert spec.weapon_type == 'bow'
    assert spec.weapon_count == 1


def test_material_recolor_changes_green_to_red_but_keeps_background(tmp_path):
    src = tmp_path / 'green.png'
    dst = tmp_path / 'red.png'
    _make_green_character(src)
    spec = parse_character_spec('female archer, change armor colors to burgundy red and gold, change cape to dark red, one bow')
    result = recolor_materials(src, dst, spec)
    assert result['ok'] is True
    assert result['changed_ratio'] > 0.05

    with Image.open(dst).convert('RGB') as im:
        # center of garment should now be red-dominant
        r, g, b = im.getpixel((120, 90))
        assert r > g * 1.5
        assert r > b * 1.3
        # background stays light gray
        bg = im.getpixel((10, 10))
        assert all(abs(c - 232) <= 3 for c in bg)
        # gold trim remains gold/yellow rather than being recolored red
        gr, gg, gb = im.getpixel((120, 125))
        assert gr > gg > gb
