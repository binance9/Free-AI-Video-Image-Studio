from app.api.character_2d_standalone import Character2DRequest
from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.command_spec import parse_command_spec
from app.modules.nhan_vat_2d.prompt_builder import build_anchor_prompt, build_negative_prompt


def test_parse_exact_dual_sword_colors():
    s = parse_command_spec(
        "male fantasy swordsman, long black hair, silver armor, purple robe, dual swords, front idle pose, gray background"
    )
    assert s.gender == "male"
    assert s.hair_color == "black"
    assert s.hair_length == "long"
    assert s.armor_color == "silver"
    assert "purple" in s.cloth_colors
    assert s.weapon_type == "sword"
    assert s.weapon_count == 2
    assert s.view == "front"
    assert s.pose == "idle"
    assert s.background_color == "gray"


def test_background_does_not_steal_armor_color():
    s = parse_command_spec("blue armor waterfall background")
    assert s.armor_color == "blue"
    assert s.background_color is None


def test_strict_prompt_prioritizes_must_haves_and_stays_short():
    p = CharacterProfile.from_prompt(
        "male fantasy swordsman, long black hair, silver armor, purple robe, dual swords, front idle pose, gray background"
    )
    prompt = build_anchor_prompt(p)
    assert "EXACTLY TWO visible swords" in prompt
    assert "one sword in each hand" in prompt
    assert "silver armor" in prompt
    assert "purple clothing" in prompt
    assert "plain gray background" in prompt
    assert len(prompt.split()) < 77


def test_strict_negative_blocks_weapon_contradictions():
    p = CharacterProfile.from_prompt("male, dual swords, silver armor")
    neg = build_negative_prompt(p)
    assert "single weapon" in neg
    assert "missing weapon" in neg
    assert "female" in neg


def test_api_allows_four_or_five_repairs_and_strict_candidates():
    req = Character2DRequest(prompt="male swordsman", max_repairs=5, strict_lock=True, candidates=3)
    assert req.max_repairs == 5
    assert req.strict_lock is True
    assert req.candidates == 3


def test_vietnamese_command_is_parsed_into_locks():
    s = parse_command_spec("nam kiếm sĩ, tóc đen dài, giáp bạc, áo tím, song kiếm, chính diện, đứng yên, nền xám")
    assert s.gender == "male"
    assert s.hair_color == "black"
    assert s.hair_length == "long"
    assert s.armor_color == "silver"
    assert "purple" in s.cloth_colors
    assert s.weapon_type == "sword"
    assert s.weapon_count == 2
    assert s.view == "front"
    assert s.pose == "idle"
    assert s.background_color == "gray"


def test_all_strict_prompt_variants_keep_critical_text_before_clip_limit():
    p = CharacterProfile.from_prompt(
        "male fantasy swordsman, long black hair, silver armor, purple robe, dual swords, front idle pose, gray background"
    )
    for variant in range(3):
        prompt = build_anchor_prompt(p, variant)
        assert len(prompt.split()) <= 76
        assert prompt.index("EXACTLY TWO visible swords") < prompt.index("professional 2D RPG")


def test_strict_preview_pipeline_runs_with_fake_engine(tmp_path):
    import io
    from PIL import Image, ImageDraw
    from app.modules.nhan_vat_2d.service import Character2DService

    class FakeEngine:
        def generate(self, prompt, style, size, quality, negative_prompt=None, seed=None):
            im = Image.new("RGB", (1024, 1536), (145, 145, 150))
            d = ImageDraw.Draw(im)
            # centered single character, black hair, silver armor, purple cloth
            d.ellipse((420, 90, 604, 280), fill=(25, 25, 25))
            d.rectangle((350, 260, 674, 820), fill=(190, 195, 205))
            d.rectangle((390, 700, 634, 1210), fill=(105, 55, 155))
            d.rectangle((405, 1180, 485, 1470), fill=(35, 35, 35))
            d.rectangle((540, 1180, 620, 1470), fill=(35, 35, 35))
            # two long sword-like edges on both sides
            d.line((300, 650, 170, 1320), fill=(230, 230, 235), width=14)
            d.line((724, 650, 854, 1320), fill=(230, 230, 235), width=14)
            buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()

    svc = Character2DService(image_service=FakeEngine(), root=tmp_path)
    profile = CharacterProfile.from_prompt(
        "male swordsman, long black hair, silver armor, purple robe, dual swords, front idle pose, gray background"
    )
    result = svc.create_anchor(profile, mode="preview", strict_lock=True, candidates=2, min_score=60)
    assert result["strict_lock"] is True
    assert result["candidate_count"] == 2
    assert len(result["candidates"]) == 2
    assert result["command_spec"]["weapon_count"] == 2
    assert result["prompt_token_guard"]["selected_prompt_words"] <= 76
