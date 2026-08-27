from PIL import Image

from app.modules.character_2d_addon.character_profile import CharacterProfile
from app.modules.character_2d_addon.prompt_builder import build_anchor_prompt, compact_user_prompt
from app.modules.character_2d_addon.quality_gate import evaluate_anchor


def test_prompt_compactor_limits_custom_words():
    p = CharacterProfile.from_prompt(" ".join(f"word{i}" for i in range(100)))
    compact = compact_user_prompt(p, 20)
    assert len(compact.split()) <= 20


def test_anchor_core_stays_first():
    p = CharacterProfile.from_prompt("silver armor red cape giant sword")
    prompt = build_anchor_prompt(p)
    assert prompt.startswith("full body 2D game sprite")
    assert "silver armor red cape giant sword" in prompt


def test_quality_gate_rejects_blank(tmp_path):
    path = tmp_path / "black.png"
    Image.new("RGB", (512, 768), (0, 0, 0)).save(path)
    result = evaluate_anchor(path)
    assert result["passed"] is False
    assert result["image"]["blank"] is True
