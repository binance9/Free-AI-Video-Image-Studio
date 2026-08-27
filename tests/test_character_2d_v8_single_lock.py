from pathlib import Path

from PIL import Image, ImageDraw

from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.prompt_builder import build_anchor_prompt, NEGATIVE_PROMPT
from app.modules.nhan_vat_2d.single_character_quality import inspect_single_character


def _make(path: Path, boxes):
    im = Image.new("RGB", (512, 768), "white")
    d = ImageDraw.Draw(im)
    for box in boxes:
        d.rectangle(box, fill=(30, 60, 120))
    im.save(path)


def test_prompt_locks_single_character():
    prompt = build_anchor_prompt(CharacterProfile.from_prompt("blue armor swordsman"))
    assert "ONE SINGLE CHARACTER ONLY" in prompt
    assert "multiple characters" in NEGATIVE_PROMPT


def test_single_center_character_passes(tmp_path: Path):
    p = tmp_path / "one.png"
    _make(p, [(180, 90, 330, 700)])
    result = inspect_single_character(p)
    assert result["ok"] is True


def test_three_characters_rejected(tmp_path: Path):
    p = tmp_path / "three.png"
    _make(p, [(20, 100, 145, 700), (190, 80, 320, 710), (365, 100, 490, 700)])
    result = inspect_single_character(p)
    assert result["ok"] is False
