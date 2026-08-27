AI VIDEO FACTORY - CHARACTER 2D V11 HARD LOCK

Muc tieu: anh chi duoc promote thanh preview.png / anchor.png / sheet.png khi qua hard gate.
Anh fail van duoc giu trong rejected/ de debug, nhung khong duoc coi la output final.

Pipeline:
user prompt -> spec_parser -> prompt_lock -> generate candidate -> base quality gate -> CLIP attribute lock
-> repair planner -> retry -> export_gate -> anchor -> frame validation -> sheet export.

Hard checks:
- single character
- full body / feet visible
- plain background
- gender neu prompt co chi dinh
- weapon type
- exactly one weapon neu prompt ghi one/single/1
- armor primary color
- sash/accent color

Cai dat:
1. Giai nen vao ai_video_factory va Replace.
2. Chay SETUP_CHARACTER_2D_V11_LOCK.bat mot lan. DreamShaper cu duoc reuse; chi them CLIP validator.
3. Chay RUN_CHARACTER_2D_ADDON.bat.
4. GET /health phai la 1.1.0.
5. Co the test /character-2d/spec truoc de xem bot parse spec.
6. Test /character-2d/preview. Neu accepted=false thi khong co preview.png final; xem blockers va best_rejected_candidate.
7. /anchor va /sheet chi export khi gate pass.
