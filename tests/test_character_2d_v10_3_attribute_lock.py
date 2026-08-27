from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.prompt_builder import NEGATIVE_PROMPT, build_anchor_prompt, build_frame_prompt


def _profile():
    return CharacterProfile.from_prompt(
        "male fantasy swordsman, blue armor, purple sash, long dark hair, clear face, one straight sword, full body"
    )


def test_mandatory_attributes_are_front_loaded():
    prompt = build_anchor_prompt(_profile()).lower()
    first_half = " ".join(prompt.split()[:35])
    for value in ["blue armor", "purple sash", "long dark hair", "one straight sword"]:
        assert value in first_half


def test_no_old_invented_defaults():
    prompt = build_anchor_prompt(_profile()).lower()
    assert "dual curved blades" not in prompt
    assert "assassin" not in prompt


def test_generic_outfit_fallback_is_discouraged():
    neg = NEGATIVE_PROMPT.lower()
    for value in ["generic sportswear", "plain bodysuit", "basic casual clothes"]:
        assert value in neg


def test_frame_keeps_mandatory_attributes():
    prompt = build_frame_prompt(_profile(), "down", "idle", 0, 1).lower()
    for value in ["blue armor", "purple sash", "long dark hair", "one straight sword"]:
        assert value in prompt


def test_anchor_stays_inside_clip_budget():
    prompt = build_anchor_prompt(_profile())
    assert len(prompt.split()) <= 75
