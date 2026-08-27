from pathlib import Path
from app.modules.nhan_vat_2d.spec_parser import parse_character_spec
from app.modules.nhan_vat_2d.reference_lock import ReferenceLibrary
from app.modules.nhan_vat_2d.prompt_lock import build_locked_prompt


def test_exact_reference_match_is_strict():
    spec=parse_character_spec("male fantasy swordsman, blue armor, purple sash, long dark hair, one sword, full body")
    spec.render_preset="compact_game"
    choice=ReferenceLibrary().choose(spec)
    assert choice.enabled
    assert choice.strict
    assert choice.strength <= 0.30


def test_sword_prompt_forbids_firearms():
    spec=parse_character_spec("male fantasy swordsman, blue armor, purple sash, long dark hair, one sword, full body")
    positive, negative=build_locked_prompt(spec)
    low=(positive+" "+negative).lower()
    assert "exactly one visible sword" in low
    assert "gun" in low
    assert "rifle" in low
    assert "camera" in low
