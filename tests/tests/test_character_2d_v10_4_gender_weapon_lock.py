from app.modules.character_2d_addon.character_profile import CharacterProfile
from app.modules.character_2d_addon.prompt_builder import NEGATIVE_PROMPT, build_anchor_prompt, build_frame_prompt


def _profile():
    return CharacterProfile.from_prompt(
        "male fantasy swordsman, blue armor, purple sash, long dark hair, clear face, one straight sword, full body"
    )


def test_male_identity_is_locked():
    prompt = build_anchor_prompt(_profile()).lower()
    assert "adult male character" in prompt
    assert "not female" in prompt


def test_one_sword_count_is_locked():
    prompt = build_anchor_prompt(_profile()).lower()
    assert "exactly one visible sword total" in prompt
    assert "no second weapon" in prompt


def test_negative_blocks_extra_blades_and_scabbard():
    neg = NEGATIVE_PROMPT.lower()
    for value in ["second sword", "two swords", "dual wielding", "dagger", "scabbard", "sheath"]:
        assert value in neg


def test_frame_keeps_gender_and_weapon_count():
    prompt = build_frame_prompt(_profile(), "down", "idle", 0, 1).lower()
    assert "adult male character" in prompt
    assert "exactly one visible sword total" in prompt


def test_anchor_prompt_stays_reasonable_for_clip():
    prompt = build_anchor_prompt(_profile())
    assert len(prompt.split()) <= 95
