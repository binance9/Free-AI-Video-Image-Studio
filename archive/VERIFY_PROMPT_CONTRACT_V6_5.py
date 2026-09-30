from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.core.prompt_contract import build_priority_prompt, fit_prompt_to_pipeline
from app.modules.tao_anh_ai.service import LocalImageService
from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.prompt_builder import build_anchor_prompt
from app.modules.ban_do_3d.cau_hinh_ban_do import resolve_quality
from app.modules.ban_do_3d.dac_ta_ban_do import parse_prompt
from app.modules.ban_do_3d.chia_o_ban_do import build_tiles
from app.modules.ban_do_3d.tao_o_ban_do import tile_prompt
from app.modules.tao_video_ai.service import LocalVideoAIService
from app.modules.ai_video_director.service import AIVideoDirectorService


class FakeTokenizer:
    model_max_length = 18

    def __call__(self, text, truncation=False, add_special_tokens=True):
        return SimpleNamespace(input_ids=[0] + list(range(len(text.split()))) + [1])


def check(condition, message):
    if not condition:
        raise AssertionError(message)


raw = (
    "beautiful polished high detail cinematic lighting professional render " * 4
    + "create one female wuxia character holding a sword full body"
)
compiled = build_priority_prompt(
    raw,
    mandatory=["EXACTLY ONE CHARACTER", "required sword must be visible"],
    quality=["photorealistic"],
    max_words=60,
    core_max_words=28,
)
fit = fit_prompt_to_pipeline(compiled, SimpleNamespace(tokenizer=FakeTokenizer()))
low = fit.text.lower()
check(fit.token_count <= 18, "tokenizer limit not respected")
check("female" in low and "sword" in low, "late user requirement lost")

with TemporaryDirectory() as temp:
    root = Path(temp)

    class Translator:
        def translate_to_english(self, _text):
            return "create one female wuxia game character holding a sword, full body, photorealistic"

    image = LocalImageService("unused", root / "models")
    image._translator = Translator()
    positive, negative = image.build_prompt("nữ kiếm hiệp cầm kiếm", "photo", "TEXT2IMG")
    p = positive.lower()
    check(p.startswith("subject and required action:"), "image core is not first")
    check("holding a sword" in p, "image sword requirement missing")
    check("exactly one character" in p, "image character count lock missing")
    check("photorealistic" in p, "image style missing")
    check("missing sword" in negative.lower(), "image negative sword guard missing")

    raw2d = " ".join(["beautiful"] * 60) + " female wuxia warrior red robe holding one sword full body"
    p2d = build_anchor_prompt(CharacterProfile.from_prompt(raw2d)).lower()
    check("sword" in p2d and "female" in p2d, "2D late requirement lost")

    quality, cfg = resolve_quality("standard")
    spec = parse_prompt("rừng phía tây, sông ở giữa, đường sang biển phía đông", quality, cfg, 8, True).as_dict()
    grid = build_tiles(8, spec["tile_size"], spec["overlap_px"])
    pmap = tile_prompt(spec, grid["tiles"][0], None).lower()
    check("sông" in pmap and "đường" in pmap and "biển" in pmap, "map user requirement lost")

    check(LocalVideoAIService._motion_bucket("hero runs and swings sword fast") == 180, "video high-motion mapping failed")
    check(LocalVideoAIService._motion_bucket("character stands still") == 90, "video low-motion mapping failed")

    director = AIVideoDirectorService(root)
    director._ollama_json = lambda *a, **k: None
    plan = director.build_plan({"idea": "một nữ kiếm hiệp cầm kiếm bước qua thành cổ", "duration_seconds": 12})
    scene = plan["scenes"][0]
    check(scene["prompt_contract"]["version"] == "1.0", "director prompt contract missing")

print("PROMPT_CONTRACT_V6_5_VERIFY: PASS")
