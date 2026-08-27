from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.direction_builder import build_pose_hint
from app.modules.nhan_vat_2d.prompt_builder import build_anchor_prompt, build_frame_prompt


def test_profile_summary_contains_core_parts():
    profile = CharacterProfile()
    text = profile.summary()
    assert "dual curved blades" in text
    assert "long high ponytail" in text


def test_pose_hint_has_direction_and_action():
    hint = build_pose_hint("down", "attack", 1, 4)
    assert "front view" in hint
    assert "impact" in hint or "swing" in hint


def test_prompt_builder_outputs_negative_prompt():
    profile = CharacterProfile.from_prompt("samurai game character")
    anchor = build_anchor_prompt(profile)
    frame = build_frame_prompt(profile, "down", "run", 0, 4)
    assert "visible eyes" in anchor
    assert "same fantasy swordsman" in frame
