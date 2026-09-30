CHARACTER 2D V13.0 — OPERATION-AWARE GATE

What changed:
- Detects operation automatically: preserve-refine / recolor-reference / reference-edit
- Recolor jobs no longer compare output colors against the old reference colors
- Recolor gate scores identity, structure, weapon, and requested target palette separately
- Target palette parser/check accepts red/burgundy + gold + cape color requests
- CLIP armor/accent/cape color false negatives are ignored during recolor when direct palette scoring passes
- UI shows compact Gate debug: operation, total score, identity, target color, weapon
- Preserve/refine mode from V12.9 remains unchanged
- Material recolor prefill from V12.8 remains unchanged

Expected /health version: 1.3.1
