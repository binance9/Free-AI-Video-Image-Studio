from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.modules.ga_brain.constraint_manager import ConstraintManager
from app.modules.ga_brain.context_manager import ConversationContextManager
from app.modules.ga_brain.core_types import IntentMode, IntentObject
from app.modules.ga_brain.executor import ToolExecutor
from app.modules.ga_brain.intent_router import IntentRouter
from app.modules.ga_brain.permission_gate import PermissionGate
from app.modules.ga_brain.planner import Planner
from app.modules.ga_brain.response_engine import ResponseEngine
from app.modules.ga_brain.service import NativeBrain
from app.modules.ga_brain.tool_registry import ToolRegistry


class ScenarioModel:
    """Deterministic model stub: production has no keyword router; tests feed intended semantic outputs."""
    def __init__(self, intents=None, plans=None, replies=None):
        self.intents = intents or {}
        self.plans = plans or {}
        self.replies = replies or {}

    def _message_from_payload(self, messages):
        try:
            return json.loads(messages[-1]["content"]).get("owner_message", "")
        except Exception:
            return ""

    def json(self, messages, fast=False, deep=False):
        system = messages[0]["content"]
        msg = self._message_from_payload(messages)
        if "Planner" in system:
            return dict(self.plans[msg])
        if "Intent Router" in system:
            return dict(self.intents[msg])
        raise AssertionError("unexpected json call")

    def chat(self, messages, fast=False, deep=False, json_mode=False):
        msg = self._message_from_payload(messages)
        return self.replies.get(msg, "Ừ, tao đang nghe.")

    def analyze_image(self, image_path, request_text=""):
        return {"available": False, "summary": None, "note": "test"}

    def describe_character_image(self, image_path):
        return {"available": False, "summary": None, "note": "test"}

    def status(self): return {"ok": True, "main_model": "qwen3:30b", "main_installed": True, "fast_installed": True}
    def vision_status(self): return {"available": False, "model": None}


def intent(mode, *, target=None, action=None, explicit=False, prospective=False, clarify=False, constraints=None, forbidden=None):
    return {
        "owner_intent": mode,
        "conversation_mode": mode,
        "target": target,
        "requested_action": action,
        "constraints": constraints or [],
        "context_references": [],
        "tools_required": [],
        "forbidden_actions": forbidden or [],
        "expected_result": "",
        "confidence": 0.99,
        "reason": "test semantic classification",
        "explicit_command": explicit,
        "prospective_only": prospective,
        "needs_clarification": clarify,
    }


def plan(tool, target, fields=None, action="run"):
    return {
        "tool_name": tool, "target": target, "action": action,
        "fields": fields or {}, "constraints": [], "forbidden_actions": [],
        "expected_result": "expected", "needs_user": "", "reason": "test plan", "confidence": 0.99,
    }


class CoreHarness:
    def __init__(self, intents, plans=None, replies=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.brain = NativeBrain(Path(self.tmp.name))
        m = ScenarioModel(intents, plans, replies)
        self.brain.models = m
        self.brain.ollama = m
        self.brain.router = IntentRouter(m)
        self.brain.registry = ToolRegistry()
        self.brain.gate = PermissionGate()
        self.brain.planner = Planner(m, self.brain.registry)
        self.brain.executor = ToolExecutor(self.brain.registry, self.brain.gate, enabled=False)
        self.brain.responses = ResponseEngine(m)
        # V12 fix: every other model-calling component above is pinned to the
        # deterministic ScenarioModel stub; constraints was the one component
        # never reassigned, so it silently called the REAL Ollama server
        # (ConstraintManager.parse()'s own except-clause just returns [] on
        # any error, which is exactly what happened when V11.3 was originally
        # certified in a sandbox with no Ollama - masking this gap). With a
        # real, reachable Ollama this is genuinely non-deterministic: a real
        # constraint parse can succeed and return actual operations for an
        # obviously constraint-bearing message, which then skips the
        # fallback path service.py uses for intent.constraints/
        # forbidden_actions and breaks test_06's fixed expected strings.
        # ScenarioModel doesn't recognize CONSTRAINT_SYSTEM prompts and
        # raises AssertionError, which parse() catches and turns into [] -
        # i.e. the exact deterministic behavior this suite was designed
        # around everywhere else.
        self.brain.constraints = ConstraintManager(m, self.brain.memory)

    def close(self): self.tmp.cleanup()


class TestGaAICoreConversation(unittest.TestCase):
    def test_01_chat_no_tool(self):
        m="ê gà"; h=CoreHarness({m:intent("CHAT")}, replies={m:"Ê, tao đây."})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["mode"],"chat"); self.assertNotIn("plan",r)
        finally:h.close()

    def test_02_question_no_tool(self):
        m="mày biết tạo ảnh 3D không?"; h=CoreHarness({m:intent("QUESTION")}, replies={m:"Biết cách chọn công cụ phù hợp, nhưng câu này chỉ là hỏi khả năng."})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["intent"]["owner_intent"],"QUESTION"); self.assertNotIn("plan",r)
        finally:h.close()

    def test_03_action_plans_but_core_locks_tool(self):
        m="tạo cho tao ảnh 3D cây kiếm"; h=CoreHarness({m:intent("ACTION",explicit=True)}, {m:plan("object_3d_generate","dovat3d",{"prompt":m})})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["intent"]["owner_intent"],"ACTION")
            self.assertEqual(r["plan"]["target"],"dovat3d")
            self.assertFalse(r["execution"]["authorized"])
            self.assertTrue(r["execution"]["core_gate_passed"])
            self.assertEqual(r["execution"]["reason"],"core_only_phase_tools_locked")
        finally:h.close()

    def test_04_analyze_does_not_edit(self):
        m="xem code này lỗi đâu"; h=CoreHarness({m:intent("ANALYZE")}, replies={m:"Có lỗi ở router; tao mới phân tích, chưa sửa."})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["intent"]["owner_intent"],"ANALYZE"); self.assertNotIn("plan",r)
            self.assertIn("chưa sửa",r["message"])
        finally:h.close()

    def test_05_follow_up_action_keeps_context(self):
        a="xem code này lỗi đâu"; b="sửa mấy lỗi đó đi"
        h=CoreHarness({a:intent("ANALYZE"),b:intent("ACTION",target="maintenance",action="sửa lỗi vừa phân tích",explicit=True)}, {b:plan("code_edit","maintenance",{"scope":"lỗi vừa phân tích"})}, {a:"Router đang sai ở bước intent."})
        try:
            h.brain.interact(a,{})
            r=h.brain.interact(b,{})
            self.assertEqual(r["plan"]["tool_name"],"code_edit")
            self.assertIsNotNone(h.brain.memory.current().get("last_analysis"))
        finally:h.close()

    def test_06_constraint_persists(self):
        m="chỉ sửa AI, không đụng bot"; h=CoreHarness({m:intent("CHAT",constraints=["chỉ sửa AI"],forbidden=["sửa file bot"])}, replies={m:"Hiểu, tao giữ giới hạn đó."})
        try:
            h.brain.interact(m,{})
            rules=" | ".join(h.brain.memory.policies())
            self.assertIn("chỉ sửa AI",rules); self.assertIn("sửa file bot",rules)
        finally:h.close()

    def test_07_truthfulness_failed_result(self):
        m="sửa file AI"; h=CoreHarness({m:intent("ACTION",explicit=True)}, {m:plan("code_edit","maintenance",{"scope":"AI"})})
        try:
            h.brain.interact(m,{})
            v=h.brain.record_tool_result({"status":"FAILED","error":"test failed","evidence":["pytest failed"]})
            self.assertEqual(v["status"],"FAILED"); self.assertFalse(v["ok"])
        finally:h.close()

    def test_08_context_chain(self):
        a="mở file AI"; b="xem phần router"; c="cái đó sai gì"; d="sửa nó"
        intents={
            a:intent("ACTION",explicit=True),
            b:intent("ANALYZE"),c:intent("ANALYZE"),
            d:intent("ACTION",target="maintenance",explicit=True),
        }
        plans={a:plan("file_read","maintenance",{"path":"AI"}),d:plan("code_edit","maintenance",{"scope":"router đang được nói tới"})}
        replies={b:"Đang xem router trong context hiện tại.",c:"Router sai ở phân loại intent."}
        h=CoreHarness(intents,plans,replies)
        try:
            h.brain.interact(a,{})
            h.brain.interact(b,{})
            h.brain.interact(c,{})
            r=h.brain.interact(d,{})
            self.assertEqual(r["plan"]["tool_name"],"code_edit")
            self.assertIn("router",h.brain.memory.current().get("last_analysis","").lower())
        finally:h.close()

    def test_09_normal_conversation(self):
        m="hôm nay tao mệt"; h=CoreHarness({m:intent("CHAT")}, replies={m:"Ừ, hôm nay nghỉ nhẹ chút cũng được."})
        try:self.assertEqual(h.brain.interact(m,{})["mode"],"chat")
        finally:h.close()

    def test_10_no_false_action(self):
        m="ảnh này mà sáng hơn chắc đẹp"; h=CoreHarness({m:intent("CHAT")}, replies={m:"Ừ, sáng hơn có thể nổi chủ thể hơn."})
        try:
            r=h.brain.interact(m,{"attachment":True,"attachment_name":"a.png"})
            self.assertNotIn("plan",r)
        finally:h.close()

    def test_11_direct_command_is_action(self):
        m="làm ảnh này sáng hơn"; h=CoreHarness({m:intent("ACTION",explicit=True)}, {m:plan("image_generate_edit","aiimage",{"prompt":m})})
        try:
            r=h.brain.interact(m,{"attachment":True,"attachment_name":"a.png"})
            self.assertEqual(r["intent"]["owner_intent"],"ACTION");self.assertEqual(r["plan"]["target"],"aiimage")
        finally:h.close()

    def test_12_change_of_mind_blocks_edit(self):
        a="sửa file A"; b="thôi chưa sửa, phân tích trước"
        h=CoreHarness({a:intent("ACTION",explicit=True),b:intent("ANALYZE",forbidden=["sửa file"])},{a:plan("code_edit","maintenance",{"scope":"A"})},{b:"Tao chỉ phân tích file A, chưa sửa."})
        try:
            h.brain.interact(a,{})
            r=h.brain.interact(b,{})
            self.assertEqual(r["intent"]["owner_intent"],"ANALYZE");self.assertNotIn("plan",r)
        finally:h.close()

    def test_13_future_talk_is_not_action(self):
        m="ok vậy giờ tao gửi lệnh cho mày rồi mày vào tạo nhé"; h=CoreHarness({m:intent("CHAT",prospective=True)},replies={m:"Ừ, khi nào mày gửi lệnh thật thì tao mới làm."})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["mode"],"chat");self.assertNotIn("plan",r)
        finally:h.close()

    def test_14_status_question_is_not_action(self):
        m="sẵn sàng tạo ảnh chưa"; h=CoreHarness({m:intent("QUESTION")},replies={m:"Sẵn sàng. Câu này chỉ là hỏi trạng thái."})
        try:self.assertEqual(h.brain.interact(m,{})["intent"]["owner_intent"],"QUESTION")
        finally:h.close()

    def test_15_continue_without_active_task_clarifies(self):
        m="giờ vào tạo đi"; h=CoreHarness({m:intent("CONTINUE",explicit=True,clarify=True)})
        try:
            r=h.brain.interact(m,{})
            self.assertEqual(r["mode"],"clarify");self.assertIn("không tự mặc định",r["message"])
        finally:h.close()

    def test_16_question_even_if_about_code_never_executes(self):
        m="mày có biết sửa code khi bot bị lỗi ko"; h=CoreHarness({m:intent("QUESTION")},replies={m:"Biết phân tích và sửa khi mày ra lệnh; câu này tao chỉ trả lời."})
        try:
            r=h.brain.interact(m,{})
            self.assertNotIn("execution",r);self.assertEqual(r["intent"]["owner_intent"],"QUESTION")
        finally:h.close()


class TestHardPermissionGate(unittest.TestCase):
    def test_chat_cannot_side_effect_even_with_plan(self):
        gate=PermissionGate(); reg=ToolRegistry(); ex=ToolExecutor(reg,gate,enabled=True)
        i=IntentObject(IntentMode.CHAT, explicit_command=False)
        p=Planner  # sentinel not used
        ok,reason=gate.authorize(i,object(),{})
        self.assertFalse(ok);self.assertEqual(reason,"intent_not_action")


if __name__ == "__main__":
    unittest.main(verbosity=2)
