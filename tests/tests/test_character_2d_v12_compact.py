from app.modules.character_2d_addon.spec_parser import parse_character_spec
from app.modules.character_2d_addon.prompt_lock import build_locked_prompt
from app.api.character_2d_standalone import Character2DRequest

def test_compact_is_default_preset():
    r=Character2DRequest(prompt="male swordsman")
    assert r.preset=="compact_game"

def test_compact_prompt_has_small_sprite_constraints():
    s=parse_character_spec("male swordsman, blue armor, one sword")
    s.render_preset="compact_game"
    pos,neg=build_locked_prompt(s)
    assert "COMPACT CHIBI-INSPIRED GAME CHARACTER PROPORTIONS" in pos
    assert "TWO THIRDS OF THE CANVAS HEIGHT" in pos
    assert "tall elongated realistic proportions" in neg

def test_spec_exposes_render_preset():
    s=parse_character_spec("male swordsman")
    assert s.render_preset=="compact_game"
