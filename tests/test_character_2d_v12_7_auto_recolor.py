from app.modules.character_2d_addon.spec_parser import parse_character_spec
from app.modules.character_2d_addon.service import _is_recolor_request
from app.modules.character_2d_addon.prompt_lock import build_locked_prompt


def test_recolor_prompt_detected():
    p = 'keep same archer, change the armor colors to burgundy red and gold, change the cape to dark red'
    assert _is_recolor_request(p) is True


def test_burgundy_gold_and_cape_are_parsed():
    spec = parse_character_spec(
        'female chibi elf archer, change the armor colors to burgundy red and gold, change the cape to dark red, keep one bow'
    )
    assert spec.gender == 'female'
    assert spec.weapon_type == 'bow'
    assert spec.weapon_count == 1
    assert spec.armor_primary == 'red'
    assert spec.accent_color == 'gold'
    assert spec.cape_color == 'red'


def test_locked_prompt_contains_recolor_targets():
    spec = parse_character_spec(
        'female chibi elf archer, change the armor colors to burgundy red and gold, change the cape to dark red, keep one bow'
    )
    positive, negative = build_locked_prompt(spec)
    assert 'PRIMARY ARMOR COLOR MUST VISIBLY BE RED' in positive
    assert 'ONE CLEAR GOLD WAIST SASH OR CLOTH ACCENT IS MANDATORY' in positive
    assert 'CAPE OR CLOAK COLOR MUST VISIBLY BE RED' in positive
    assert 'EXACTLY ONE VISIBLE BOW TOTAL' in positive
