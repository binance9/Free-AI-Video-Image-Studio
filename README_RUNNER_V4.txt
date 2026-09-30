V11.3 REAL MODEL RUNNER V4 - CASE ISOLATION

ONLY real_model_behavior.py is changed. AI Core untouched.
- qwen3:30b real model still drives IntentRouter/ConstraintManager/Planner.
- ResponseEngine prose call is suppressed in runner only so CHAT/QUESTION tests do not make an irrelevant second 30B request.
- HTTP transport timeout: 50s.
- Hard wall-clock timeout per standalone case: 60s via spawned child process terminate/kill.
- Timeout/error is recorded and suite continues.
- Expected labels and V11.3 thresholds unchanged.
