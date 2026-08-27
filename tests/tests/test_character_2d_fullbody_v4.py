from pathlib import Path

from PIL import Image, ImageDraw

from app.modules.character_2d_addon.face_refiner import _fallback_head_box
from app.modules.character_2d_addon.fullbody_quality import inspect_fullbody
from app.modules.character_2d_addon.prompt_builder import NEGATIVE_PROMPT, build_anchor_prompt
from app.modules.character_2d_addon.character_profile import CharacterProfile


def test_anchor_prompt_locks_full_body():
    prompt = build_anchor_prompt(CharacterProfile())
    assert "entire body visible" in prompt
    assert "both feet visible" in prompt
    assert "portrait" in NEGATIVE_PROMPT
    assert "upper body only" in NEGATIVE_PROMPT


def test_fallback_face_box_does_not_reach_chest():
    box = _fallback_head_box((1024, 1536))
    assert box[3] < 1536 * 0.30
    assert (box[2] - box[0]) < 1024 * 0.40


def test_fullbody_checker_accepts_lower_detail(tmp_path: Path):
    p = tmp_path / "full.png"
    im = Image.new("RGB", (512, 768), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((190, 80, 320, 680), fill="black")
    d.rectangle((180, 620, 230, 750), fill="black")
    d.rectangle((280, 620, 330, 750), fill="black")
    im.save(p)
    result = inspect_fullbody(p)
    assert result["score"] > 0
    assert result["feet_edge"] > 0
