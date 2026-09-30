from pathlib import Path
import sys
root=Path(__file__).resolve().parent
auto=root/'app/modules/ai_video_director/auto_producer.py'
quality=root/'app/modules/ai_video_director/quality.py'
if not auto.is_file() or not quality.is_file():
    raise SystemExit('FAIL: khong tim thay app/modules/ai_video_director')
t=auto.read_text(encoding='utf-8', errors='ignore')
checks={
 'marker_v652': 'FPS FIX V6.5.2 ACTIVE' in t,
 'normalize_before_qa': 'Chuẩn hóa CFR 30fps trước VIDEO QA' in t,
 'fps_mode_cfr': '"-fps_mode", "cfr"' in t,
 'normalized_gate': 'qa_gate": "normalized_cfr"' in t,
}
for k,v in checks.items(): print(k, 'PASS' if v else 'FAIL')
if not all(checks.values()): raise SystemExit(2)
print('V6.5.2 FPS runtime files: PASS')
