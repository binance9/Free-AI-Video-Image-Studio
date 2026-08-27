from app.api.character_2d_standalone import Character2DRequest
from app.modules.nhan_vat_2d.character_profile import CharacterProfile
from app.modules.nhan_vat_2d.prompt_builder import build_anchor_prompt, build_negative_prompt

prompt = "male fantasy swordsman, long black hair, silver armor, purple robe, dual swords, front idle pose, gray background"
req = Character2DRequest(prompt=prompt, max_repairs=4, strict_lock=True, candidates=2)
p = CharacterProfile.from_prompt(prompt)
compiled = build_anchor_prompt(p)
neg = build_negative_prompt(p)
spec = p.command_spec()
assert req.max_repairs == 4
assert spec.weapon_count == 2 and spec.weapon_type == "sword"
assert spec.armor_color == "silver" and "purple" in spec.cloth_colors
assert "EXACTLY TWO visible swords" in compiled
assert "one sword in each hand" in compiled
assert len(compiled.split()) < 77
assert "single weapon" in neg and "missing weapon" in neg
print("[PASS] Character 2D V11 strict command lock")
print("compiled_words=", len(compiled.split()))
print("spec=", spec.to_dict())
