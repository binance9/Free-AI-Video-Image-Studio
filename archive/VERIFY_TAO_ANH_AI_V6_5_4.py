import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.tao_anh_ai.service import LocalImageService, _extract_character_constraints

svc = LocalImageService('dummy-model', ROOT / '_verify_model_cache')
# Verify code only. Do not depend on Ollama/translator during installation.
svc._translate = lambda _text: 'Create a realistic image of a female wuxia warrior holding a sword, full body.'
source = 'tạo 1 nữ kiếm hiệp cầm 1 thanh kiếm, toàn thân, ảnh thật'
positive, negative = svc.build_prompt(source, 'photo', 'TEXT2IMG')
constraints = _extract_character_constraints(source, source, 'photo')

need_positive = [
    'EXACTLY ONE CHARACTER ONLY',
    'ONE PERSON, ONE POSE, ONE CAMERA VIEW',
    'not a character sheet or lineup',
    'female wuxia swordswoman',
    'holding ONE complete visible sword',
    'full body standing',
    'No wings',
]
need_negative = [
    'character sheet', 'model sheet', 'turnaround', 'lineup', 'multi-view',
    'multiple poses', 'missing sword', 'wrong weapon', 'close-up', 'wings', '3D render',
]
missing = [item for item in need_positive if item not in positive]
missing += [item for item in need_negative if item not in negative]

if not constraints.get('anti_sheet') or not constraints.get('full_body') or not constraints.get('sword'):
    missing.append('constraint extraction')

if missing:
    print('TAO_ANH_AI_V6_5_4_VERIFY: FAIL')
    print('POSITIVE:', positive)
    print('NEGATIVE:', negative)
    print('MISSING:', missing)
    raise SystemExit(1)

print('TAO_ANH_AI_V6_5_4_VERIFY: PASS')
print('POSITIVE:', positive)
print('NEGATIVE_PRIORITY: PASS')
print('SINGLE_SUBJECT_CONSTRAINT: PASS')
