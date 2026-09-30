# GÀ AI CORE V12 — FAST + NATURAL BRAIN ROUTER

CORE_VERSION = `V12`. Builds on V11.3 (`ARCHITECTURE_V11_3.md`) without touching
any safety/permission/verifier logic. Scope is still AI Core only: bot
ảnh/3D is NOT connected in this version, real tool execution is still
disabled (`ToolExecutor(enabled=False)`).

## What changed vs V11.3

V11.3 hardcoded `fast=False, deep=False` at every single model call site
(`constraint_manager.py`, `intent_router.py`, `response_engine.py`,
`planner.py`) — every message, including "ê gà"/"ok"/"tiếp", triggered 2-4
sequential real `qwen3:30b` calls per turn. V12 adds one new module,
**`model_router.py`**, and wires it into those same 4 call sites without
changing any of their system prompts, JSON schemas, or safety gates.

### `ModelRouter` (new)

- **Structural routing, not semantic keyword-matching.** Decides fast
  (`qwen3:8b`) vs deep (`qwen3:30b`) using message length/shape and whether
  the active task already looks complex — never by guessing intent itself
  (that stays the LLM's job, unchanged).
- **Confidence-based escalation.** Intent classification and planning both
  already return a `confidence` field in their existing JSON schema. If a
  FAST pass comes back with `confidence < 0.72`, or a FAST intent call
  resolves to `ACTION` with `confidence < 0.90`, the router re-runs that
  exact same call on the DEEP model with the FULL (uncompressed) context
  before trusting the result. This is the "escalate if unsure" mechanism —
  never a keyword heuristic.
- **Per-stage decisions:**
  - `constraint` → always FAST (bounded, small extraction; no accuracy
    benchmark in the existing suite depends on 30B for this).
  - `intent` → FAST unless the message is long/code-like, with the
    confidence escalation above.
  - `response` → FAST for CHAT/QUESTION, DEEP (+ thinking) for ANALYZE
    (matches the code-review/analysis category in the task spec).
  - `planner` → FAST for a single-tool, short request; DEEP if the plan
    needs >1 tool, the message is long/code-like, or the FAST attempt
    failed/returned a low-confidence plan.
- **Fallback on 30B failure.** If a DEEP call raises (timeout or Ollama
  error), the router retries once on FAST before giving up — so a stuck 30B
  never causes an indefinite hang, and the caller's own existing
  safe-fallback (`SAFE_FALLBACK` intent, `planner_unavailable`, etc.) is
  still the last resort if that retry also fails. No result is ever
  fabricated.
- **Structured logging.** Every routed call is recorded as
  `{stage, model_used, route_reason, latency_ms, thinking_mode, escalated,
  fallback}`. `NativeBrain.route_stats()` / `route_log()` expose rollups;
  `GET /api/ga-brain/route-stats` and the `route_stats` field on
  `GET /api/ga-brain/status` surface them over HTTP.

### Context compression (`compact_context()`)

FAST-routed calls send a trimmed `recent_turns` window (last 6 turns)
instead of V11.3's fixed last-20 window. Every structured session field a
reference/continuation/constraint decision could need — `active_task`,
`current_target`, `current_files`, `references_map`, `active_constraints`,
`last_analysis`/`last_identified_problems`, `pending_plan`,
`last_execution_result`, `cancelled_tasks` — is sent byte-for-byte regardless
of route. DEEP-routed calls always get the full, uncompressed snapshot,
identical to V11.3.

### Natural response

`RESPONSE_SYSTEM` (response_engine.py) is unchanged from V11.3: no template
reuse, no unsolicited elaboration, truthful about not having run a tool yet.
V12 does not touch this prompt — the "natural response" requirement is
already satisfied by an existing, tested system prompt; what V12 adds is
simply *not spending 30B reasoning time* on delivering it for a simple
message.

## What did NOT change

- `INTENT_SYSTEM`, `PLANNER_SYSTEM`, `CONSTRAINT_SYSTEM`, `RESPONSE_SYSTEM` —
  byte-identical to V11.3.
- `PermissionGate`, `RequirementValidator`, `ExecutionManager`, `ToolExecutor`,
  `ResultVerifier` — untouched.
- The ACTION explicit-command gate, the CONTINUE active-task check, the
  unauthorized-action denominator (CHAT/QUESTION/ANALYZE only) — untouched.
- Tool execution is still `enabled=False` (core-only phase).

## Real test-harness bug found and fixed along the way

`tests/test_ai_core.py`'s `CoreHarness` pins every model-calling component
(`IntentRouter`, `Planner`, `ResponseEngine`) to a deterministic
`ScenarioModel` stub — except `ConstraintManager`, which was never
reassigned and so always called the REAL Ollama server. This was invisible
in the original V11.3 certification because that run's sandbox had no
Ollama reachable (`TEST_REPORT_V11_3.md`: `REAL_MODEL_TEST_NOT_RUN` /
`ollama_unavailable`), so `ConstraintManager.parse()`'s own
`except Exception: return []` always fired, coincidentally matching what the
tests expected. With a real, reachable Ollama (this machine), a real
constraint parse can genuinely extract an operation from an obviously
constraint-bearing test message, which then skips the fallback path
`service.py` uses to persist `intent.constraints`/`forbidden_actions` from
the test's fixed `ScenarioModel` data — breaking `test_06_constraint_persists`
non-deterministically. Verified this was model-independent (a direct
`fast=False` call reproduced the same class of issue) before concluding it
was a harness gap, not a V12 regression. Fixed by completing the mock
wiring `CoreHarness` was clearly already doing for every other component
(`self.brain.constraints = ConstraintManager(m, self.brain.memory)`) — no
assertion or expected value was changed.

## Files changed/added

- `app/modules/ga_brain/model_router.py` — **new**.
- `app/modules/ga_brain/model_client.py` — added `resolve_model()` (thin
  public wrapper over the existing `_choose_model()`, for router logging).
- `app/modules/ga_brain/intent_router.py`, `response_engine.py`,
  `planner.py`, `constraint_manager.py` — now route through `ModelRouter`
  instead of the hardcoded `fast=False, deep=False`. Prompts/schemas
  unchanged.
- `app/modules/ga_brain/service.py` — constructs one shared `ModelRouter`,
  passes it into the 4 components above; `CORE_VERSION` bumped to `V12`;
  added `route_stats()`/`route_log()`.
- `app/modules/ga_brain/api_ga_brain.py` — `BUILD_VERSION` bumped;
  `route_stats` added to `/status`; new `GET /route-stats`.
- `app/modules/ga_brain/tests/test_ai_core.py` — test-harness bug fix
  described above (mock wiring only, no assertions changed).
- `app/modules/ga_brain/tests/benchmark_v12.py` — **new**: real 50/30/20
  latency + routing benchmark, with `--smoke` mode (10-20 cases).
- `app/modules/ga_brain/ARCHITECTURE_V12.md` — this file.
