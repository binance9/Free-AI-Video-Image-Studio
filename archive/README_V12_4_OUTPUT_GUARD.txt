CHARACTER 2D V12.4 OUTPUT GUARD

Added in this patch:
- Detects black / blank / fully transparent output before accepting export
- Retry prompts now add bright-background and no-black-frame repair hints
- Accepted preview / anchor / reference-result exports are flattened onto a light gray background
  so Windows image viewers do not show them as black when alpha is present
- Version bumped to 1.2.4

Main files changed:
- app/app/modules/character_2d_addon/output_guard.py
- app/app/modules/character_2d_addon/quality_gate.py
- app/app/modules/character_2d_addon/export_gate.py
- app/app/modules/character_2d_addon/repair_planner.py
- app/app/modules/character_2d_addon/service.py
- app/app/api/character_2d_standalone.py
