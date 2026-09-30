from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

# --- V12 FAST + NATURAL BRAIN ROUTER -----------------------------------------
# Decides qwen3:8b ("fast") vs qwen3:30b ("deep") + thinking on/off per
# pipeline stage (constraint parse / intent classify / response / planner).
#
# This is a STRUCTURAL/CONFIDENCE router, not a semantic classifier: it never
# guesses owner_intent itself (that stays the LLM's job in intent_router.py,
# unchanged) and never keyword-matches meaning. It only decides HOW MUCH
# model to spend on a given call, using:
#   1. cheap structural signals (message length, code-like shape, whether the
#      active task already looks complex) computed BEFORE any model call, and
#   2. the model's OWN confidence score (already part of the existing
#      IntentObject/ActionPlan schemas) to ESCALATE fast->deep after the fact
#      when the fast pass wasn't sure - never the other way silently.
#
# Safety posture: when in doubt this module always resolves toward "deep" or
# toward "escalate", never toward skipping/softening an existing safety check.
# It does not touch INTENT_SYSTEM/PLANNER_SYSTEM/CONSTRAINT_SYSTEM prompts,
# the ACTION explicit-command gate, or any permission/verifier logic.

_CODE_MARKERS = re.compile(r"```|\bdef \b|\bclass \b|\bfunction\b|=>|;\s*$|^\s*(import|from)\s|\{\s*$", re.M)
_LONG_INPUT_CHARS = 220
_LONG_INPUT_LINES = 3
_ESCALATION_CONFIDENCE = 0.72
_ACTION_RECONFIRM_CONFIDENCE = 0.90


@dataclass
class RouteDecision:
    stage: str
    fast: bool
    deep: bool
    reason: str
    escalated: bool = False

    @property
    def thinking_mode(self) -> bool:
        return bool(self.deep)


@dataclass
class RouteLogEntry:
    stage: str
    model_used: str
    route_reason: str
    latency_ms: float
    thinking_mode: bool
    escalated: bool = False
    fallback: bool = False
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "model_used": self.model_used,
            "route_reason": self.route_reason,
            "latency_ms": round(self.latency_ms, 1),
            "thinking_mode": self.thinking_mode,
            "escalated": self.escalated,
            "fallback": self.fallback,
            "at": self.at,
        }


def _looks_structurally_complex(message: str, context: dict | None) -> bool:
    text = str(message or "")
    if len(text) > _LONG_INPUT_CHARS or text.count("\n") >= _LONG_INPUT_LINES:
        return True
    if _CODE_MARKERS.search(text):
        return True
    ctx = context if isinstance(context, dict) else {}
    active_task = ctx.get("active_task")
    if isinstance(active_task, dict):
        task_msg = str(active_task.get("message") or "")
        if len(task_msg) > _LONG_INPUT_CHARS:
            return True
    return False


def compact_context(ctx: dict, turns_limit: int = 6) -> dict:
    """Context compression for FAST-routed prompts (requirement #5): keep every
    structured field a reference/continuation/constraint decision might need
    (active_task, current_target, current_files, references_map,
    active_constraints, last_analysis/problems, pending_plan, last result,
    cancelled_tasks) byte-for-byte, and only trim the bulky raw turn-by-turn
    chat log to the last `turns_limit` entries. Never used for DEEP-routed
    calls, which still get the full snapshot exactly as V11.3 did."""
    if not isinstance(ctx, dict):
        return ctx
    out = dict(ctx)
    turns = out.get("recent_turns")
    if isinstance(turns, list) and len(turns) > turns_limit:
        out["recent_turns"] = turns[-turns_limit:]
    return out


def _safe_resolve_model(model_client, fast: bool) -> str:
    """A 'model client' only has to provide .chat()/.json() to work with the
    rest of ga_brain (see tests/test_ai_core.py's ScenarioModel stub, which
    predates this router and has neither resolve_model() nor _choose_model()).
    resolve_model() is a nice-to-have for logging only - never a hard
    requirement - so degrade to a best-effort label instead of raising."""
    resolver = getattr(model_client, "resolve_model", None)
    if callable(resolver):
        try:
            return str(resolver(fast=fast))
        except Exception:
            pass
    attr = "fast_model" if fast else "main_model"
    name = getattr(model_client, attr, None)
    if name:
        return str(name)
    return "fast" if fast else "deep"


class ModelRouter:
    """Shared per-brain router instance. Stateless decisions, but keeps a
    bounded rolling log of every routed call for /status + benchmark
    reporting (requirement: log model_used/route_reason/latency_ms/
    thinking_mode, and produce route statistics)."""

    MAX_LOG = 1000

    def __init__(self):
        self.log: list[RouteLogEntry] = []

    # ---- stage-specific routing -------------------------------------------------
    def route_constraint(self, message: str, context: dict) -> RouteDecision:
        # Constraint parsing is a small bounded extraction (ADD/REPLACE/REVOKE/
        # CLEAR over a short message) - always cheap, never needs 30B. If the
        # message itself looks complex we still let intent/response escalate;
        # constraint parsing does not get materially more accurate from 30B.
        return RouteDecision("constraint", fast=True, deep=False, reason="lightweight_bounded_extraction")

    def route_intent(self, message: str, context: dict) -> RouteDecision:
        if _looks_structurally_complex(message, context):
            return RouteDecision("intent", fast=False, deep=False, reason="structural_complexity")
        return RouteDecision("intent", fast=True, deep=False, reason="short_simple_input")

    def escalate_intent(self, decision: RouteDecision, confidence: float, owner_intent: str) -> RouteDecision | None:
        """Requirement #7: escalate FAST->DEEP on low confidence or a
        borderline ACTION call, using the model's own confidence field -
        never a keyword guess. Returns None when no escalation is needed."""
        if not decision.fast:
            return None
        conf = float(confidence or 0.0)
        if conf < _ESCALATION_CONFIDENCE:
            return RouteDecision("intent", fast=False, deep=False, reason=f"low_confidence_{conf:.2f}", escalated=True)
        if owner_intent == "ACTION" and conf < _ACTION_RECONFIRM_CONFIDENCE:
            # Extra caution specifically for ACTION: a false positive here is
            # the one category that could authorize a real side effect once
            # tools are connected in a later phase.
            return RouteDecision("intent", fast=False, deep=False, reason=f"action_safety_reconfirm_{conf:.2f}", escalated=True)
        return None

    def route_response(self, owner_intent: str, message: str, context: dict) -> RouteDecision:
        if owner_intent == "ANALYZE":
            return RouteDecision("response", fast=False, deep=True, reason="analyze_deep_reasoning")
        if _looks_structurally_complex(message, context):
            return RouteDecision("response", fast=False, deep=False, reason="structural_complexity")
        return RouteDecision("response", fast=True, deep=False, reason="chat_or_question_fast")

    def route_planner(self, message: str, context: dict, intent) -> RouteDecision:
        tools_needed = len(getattr(intent, "tools_required", None) or [])
        if _looks_structurally_complex(message, context) or tools_needed > 1:
            return RouteDecision("planner", fast=False, deep=False, reason="multi_step_or_complex_plan")
        return RouteDecision("planner", fast=True, deep=False, reason="single_step_plan")

    def escalate_planner(self, decision: RouteDecision, confidence: float | None, has_error: bool) -> RouteDecision | None:
        if not decision.fast:
            return None
        if has_error:
            return RouteDecision("planner", fast=False, deep=False, reason="plan_build_failed_retry_deep", escalated=True)
        conf = float(confidence or 0.0)
        if conf < _ESCALATION_CONFIDENCE:
            return RouteDecision("planner", fast=False, deep=False, reason=f"plan_low_confidence_{conf:.2f}", escalated=True)
        return None

    # ---- timed call wrapper with fallback -----------------------------------
    def call_json(self, model_client, decision: RouteDecision, messages: list[dict]) -> tuple[dict, RouteLogEntry]:
        """Runs model_client.json(...) under `decision`, times it, logs it, and
        applies requirement #8's fallback: if a DEEP (30B) call raises (timeout
        or Ollama error), retry once on FAST (8B) rather than hang/propagate -
        the caller's own existing safe-fallback (SAFE_FALLBACK intent /
        planner_unavailable / etc.) still applies if that retry also fails, so
        no result is ever fabricated."""
        model_name = _safe_resolve_model(model_client, decision.fast)
        started = time.perf_counter()
        fallback = False
        try:
            obj = model_client.json(messages, fast=decision.fast, deep=decision.deep)
        except Exception:
            if not decision.fast:
                fallback = True
                model_name = _safe_resolve_model(model_client, True)
                obj = model_client.json(messages, fast=True, deep=False)
            else:
                raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        entry = RouteLogEntry(decision.stage, model_name, decision.reason if not fallback else f"{decision.reason}+deep_call_failed_fallback_fast", latency_ms, decision.thinking_mode and not fallback, decision.escalated, fallback)
        self._append(entry)
        return obj, entry

    def call_chat(self, model_client, decision: RouteDecision, messages: list[dict]) -> tuple[str, RouteLogEntry]:
        model_name = _safe_resolve_model(model_client, decision.fast)
        started = time.perf_counter()
        fallback = False
        try:
            text = model_client.chat(messages, fast=decision.fast, deep=decision.deep)
        except Exception:
            if not decision.fast:
                fallback = True
                model_name = _safe_resolve_model(model_client, True)
                text = model_client.chat(messages, fast=True, deep=False)
            else:
                raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        entry = RouteLogEntry(decision.stage, model_name, decision.reason if not fallback else f"{decision.reason}+deep_call_failed_fallback_fast", latency_ms, decision.thinking_mode and not fallback, decision.escalated, fallback)
        self._append(entry)
        return text, entry

    def _append(self, entry: RouteLogEntry):
        self.log.append(entry)
        if len(self.log) > self.MAX_LOG:
            del self.log[: len(self.log) - self.MAX_LOG]

    # ---- reporting ----------------------------------------------------------
    def stats(self) -> dict:
        if not self.log:
            return {"count": 0}
        by_model: dict[str, int] = {}
        by_stage: dict[str, dict[str, Any]] = {}
        escalations = 0
        fallbacks = 0
        total_latency = 0.0
        for e in self.log:
            by_model[e.model_used] = by_model.get(e.model_used, 0) + 1
            st = by_stage.setdefault(e.stage, {"count": 0, "total_latency_ms": 0.0, "deep_calls": 0})
            st["count"] += 1
            st["total_latency_ms"] += e.latency_ms
            if e.thinking_mode:
                st["deep_calls"] += 1
            if e.escalated:
                escalations += 1
            if e.fallback:
                fallbacks += 1
            total_latency += e.latency_ms
        for st in by_stage.values():
            st["avg_latency_ms"] = round(st["total_latency_ms"] / st["count"], 1) if st["count"] else 0.0
        return {
            "count": len(self.log),
            "by_model": by_model,
            "by_stage": by_stage,
            "escalations": escalations,
            "fallbacks": fallbacks,
            "avg_latency_ms": round(total_latency / len(self.log), 1),
        }

    def recent(self, limit: int = 50) -> list[dict]:
        return [e.to_dict() for e in self.log[-limit:]]
