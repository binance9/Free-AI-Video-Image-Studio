from app.modules.character_2d_addon.prompt_builder import build_anchor_prompt, build_repair_prompt
from app.modules.character_2d_addon.character_profile import CharacterProfile
from app.modules.character_2d_addon.background_quality import inspect_background
from PIL import Image
from pathlib import Path


def test_anchor_prompt_contains_game_ready_terms():
    profile = CharacterProfile.from_prompt("blue armor waterfall background")
    prompt = build_anchor_prompt(profile)
    assert "full body 2D game sprite sheet character" in prompt
    assert "plain clean background" in prompt


def test_repair_prompt_handles_background_issue():
    profile = CharacterProfile.from_prompt("blue armor")
    prompt = build_repair_prompt(profile, ["background"])
    assert "remove scenery" in prompt


def test_background_quality_on_plain_canvas(tmp_path: Path):
    img = Image.new("RGB", (512, 768), (240, 240, 240))
    path = tmp_path / "plain.png"
    img.save(path)
    result = inspect_background(path)
    assert result["ok"] is True
