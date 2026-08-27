from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.prompt_builder import NEGATIVE_PROMPT, build_anchor_prompt


def test_exact_design_not_replaced_by_old_defaults():
    p = CharacterProfile.from_prompt("male fantasy swordsman, blue armor, purple sash, long dark hair, one straight sword")
    prompt = build_anchor_prompt(p).lower()
    assert "blue armor" in prompt
    assert "purple sash" in prompt
    assert "long dark hair" in prompt
    assert "dual curved blades" not in prompt
    assert "assassin" not in prompt


def test_background_ui_is_strongly_excluded():
    neg = NEGATIVE_PROMPT.lower()
    for word in ["text", "logo", "user interface", "menu", "panel", "screenshot"]:
        assert word in neg


def test_anchor_is_kept_short_for_clip():
    p = CharacterProfile.from_prompt("male fantasy swordsman blue armor purple sash long dark hair clear face one straight sword silver boots leather belt")
    prompt = build_anchor_prompt(p)
    assert len(prompt.split()) <= 75
