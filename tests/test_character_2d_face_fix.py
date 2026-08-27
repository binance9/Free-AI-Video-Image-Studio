from app.modules.character_2d_addon.character_profile import CharacterProfile
from app.modules.character_2d_addon.prompt_builder import NEGATIVE_PROMPT, build_anchor_prompt, build_face_refine_prompt


def test_anchor_prompt_is_short_for_sd15_clip():
    prompt = build_anchor_prompt(CharacterProfile())
    assert len(prompt.split()) < 77
    assert "visible eyes" in prompt


def test_face_refine_prompt_requires_features():
    prompt = build_face_refine_prompt(CharacterProfile())
    assert "pupils" in prompt
    assert "nose" in prompt
    assert "lips" in prompt
    assert "faceless" in NEGATIVE_PROMPT
