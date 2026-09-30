"""V14 - Visual Intent Interpreter for character image beauty/style language.

No network calls: the model client is stubbed so these tests verify real
parsing/merge/patch logic (section 24's own instruction), not Ollama itself.
"""
from __future__ import annotations

import unittest

from app.modules.nhan_vat_2d.visual_intent import (
    VisualIntentInterpreter, apply_beauty_preset, FEMALE_FANTASY_BEAUTY_V1, MALE_HERO_V1,
)
from app.modules.nhan_vat_2d.spec_parser import CharacterSpec, parse_character_spec
from app.modules.nhan_vat_2d.prompt_lock import build_locked_prompt


class StubModel:
    """Returns a fixed JSON dict regardless of input, or raises if configured
    to simulate a provider error - never touches the network."""
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0

    def json(self, messages, **kw):
        self.calls += 1
        if self.raise_exc:
            raise self.raise_exc
        return self.response


def interpreter(response=None, raise_exc=None):
    return VisualIntentInterpreter(StubModel(response=response, raise_exc=raise_exc))


class TestVisualIntentParsing(unittest.TestCase):
    def test_A_beauty_archer_request(self):
        resp = {"is_patch": False, "beauty_priority": True,
                "face_beauty": ["delicate face"], "body_style": ["slim elegant"],
                "hair_style": [], "costume_style": [], "pose_style": [],
                "camera_style": ["flattering perspective"], "lighting_style": ["soft light"],
                "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("tạo một nữ cung thủ đẹp kiểu tiên hiệp")
        self.assertTrue(out["beauty_priority"])
        self.assertIn("delicate face", out["face_beauty"])
        self.assertIn("slim elegant", out["body_style"])
        self.assertEqual(out["preserve"], [])

    def test_B_patch_face_only_keeps_other_fields_empty(self):
        resp = {"is_patch": True, "beauty_priority": True,
                "face_beauty": ["prettier face", "brighter eyes"], "body_style": [],
                "hair_style": [], "costume_style": [], "pose_style": [], "camera_style": [],
                "lighting_style": [], "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("cho mặt nó xinh hơn")
        self.assertTrue(out["is_patch"])
        self.assertIn("prettier face", out["face_beauty"])
        self.assertEqual(out["hair_style"], [])
        self.assertEqual(out["costume_style"], [])

    def test_C_leg_length_patch_preserves_face(self):
        resp = {"is_patch": True, "beauty_priority": False,
                "face_beauty": [], "body_style": ["visibly longer legs"],
                "hair_style": [], "costume_style": [], "pose_style": [], "camera_style": [],
                "lighting_style": [], "render_style": [], "preserve": ["face"]}
        out = interpreter(resp).interpret("chân dài hơn nhưng giữ nguyên mặt")
        self.assertIn("face", out["preserve"])
        self.assertIn("visibly longer legs", out["body_style"])
        spec = CharacterSpec(raw_prompt="chân dài hơn nhưng giữ nguyên mặt", gender="female")
        merged = apply_beauty_preset(out, spec.gender, spec.raw_prompt)
        self.assertEqual(merged.get("face_beauty"), [])

    def test_D_muscular_male_warrior_does_not_get_female_preset(self):
        resp = {"is_patch": False, "beauty_priority": True,
                "face_beauty": [], "body_style": ["muscular"], "hair_style": [],
                "costume_style": [], "pose_style": [], "camera_style": [], "lighting_style": [],
                "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("làm nam chiến binh cơ bắp")
        merged = apply_beauty_preset(out, "male", "làm nam chiến binh cơ bắp")
        # "cơ bắp" (muscular) is an off-preset marker - no female/male beauty
        # preset should be force-merged on top of an explicit muscular request.
        for key in FEMALE_FANTASY_BEAUTY_V1:
            self.assertNotEqual(merged.get(key), FEMALE_FANTASY_BEAUTY_V1[key])

    def test_E_chibi_request_not_forced_to_75_heads(self):
        resp = {"is_patch": False, "beauty_priority": True, "face_beauty": [], "body_style": [],
                "hair_style": [], "costume_style": [], "pose_style": [], "camera_style": [],
                "lighting_style": [], "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("tạo nhân vật chibi")
        merged = apply_beauty_preset(out, "female", "tạo nhân vật chibi")
        self.assertEqual(merged.get("body_style"), [])

    def test_F_premium_does_not_change_identity_fields(self):
        resp = {"is_patch": True, "beauty_priority": True, "face_beauty": [],
                "body_style": [], "hair_style": [], "costume_style": ["premium refined materials"],
                "pose_style": [], "camera_style": [], "lighting_style": ["clean controlled highlights"],
                "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("cho nó sang hơn")
        self.assertIn("premium refined materials", out["costume_style"])
        # Interpreter output never carries gender/weapon fields at all - those
        # stay owned exclusively by the deterministic parser.
        self.assertNotIn("gender", out)
        self.assertNotIn("weapon_type", out)

    def test_provider_error_returns_empty_not_crash(self):
        out = interpreter(raise_exc=RuntimeError("ollama down")).interpret("tạo nữ cung thủ đẹp")
        # Keyword backstop still fires even when the LLM call itself failed -
        # "đẹp" is a BEAUTY_TRIGGER_WORDS hit - so apply_beauty_preset's
        # generic preset remains available as a floor, but no descriptor
        # content is fabricated (face_beauty stays empty; only the priority
        # flag is keyword-derived).
        self.assertTrue(out["beauty_priority"])
        self.assertEqual(out["face_beauty"], [])

    def test_provider_error_without_trigger_word_stays_false(self):
        out = interpreter(raise_exc=RuntimeError("ollama down")).interpret("tạo một hiệp sĩ cầm khiên")
        self.assertFalse(out["beauty_priority"])

    def test_invalid_response_shape_returns_empty(self):
        out = interpreter(response="not a dict").interpret("tạo nữ cung thủ đẹp")
        self.assertEqual(out["face_beauty"], [])

    def test_missing_fields_default_to_empty(self):
        out = interpreter({"beauty_priority": True}).interpret("tạo nữ cung thủ đẹp")
        self.assertTrue(out["beauty_priority"])
        self.assertEqual(out["face_beauty"], [])
        self.assertEqual(out["preserve"], [])

    def test_beauty_priority_derived_when_model_forgets_the_flag(self):
        # Real observed behavior (2026-08-29): qwen3:30b populated rich
        # face_beauty/body_style/etc content but still answered
        # beauty_priority=false for the same message. Never trust the
        # model's own summary flag over what it actually produced.
        resp = {"is_patch": False, "beauty_priority": False,
                "face_beauty": ["delicate facial structure"], "body_style": ["slender frame"],
                "hair_style": [], "costume_style": [], "pose_style": [], "camera_style": [],
                "lighting_style": [], "render_style": [], "preserve": []}
        out = interpreter(resp).interpret("tạo một nữ cung thủ đẹp kiểu tiên hiệp")
        self.assertTrue(out["beauty_priority"])

    def test_short_message_never_calls_model(self):
        model = StubModel(response={"beauty_priority": True})
        VisualIntentInterpreter(model).interpret("a")
        self.assertEqual(model.calls, 0)


class TestPromptBuilderIntegration(unittest.TestCase):
    def test_beauty_fields_appear_in_final_prompt_without_contradiction(self):
        spec = parse_character_spec("nữ cung thủ tóc đen")
        spec.face_beauty = ["delicate youthful facial features", "soft V-shaped jawline"]
        spec.body_style = ["long elegant legs", "relatively small refined head"]
        spec.hair_style = ["layered flowing hair"]
        spec.lighting_style = ["soft cinematic key and fill lighting"]
        positive, negative = build_locked_prompt(spec)
        for phrase in spec.face_beauty + spec.body_style + spec.hair_style + spec.lighting_style:
            self.assertIn(phrase, positive)
        self.assertNotIn("short legs", positive.lower())
        self.assertNotIn("large head", positive.lower())
        self.assertIn("oversized head", negative)  # BEAUTY_NEGATIVE merged in

    def test_no_beauty_fields_no_beauty_negative(self):
        spec = parse_character_spec("nữ cung thủ tóc đen")
        _, negative = build_locked_prompt(spec)
        self.assertNotIn("oversized head", negative)


if __name__ == "__main__":
    unittest.main(verbosity=2)
