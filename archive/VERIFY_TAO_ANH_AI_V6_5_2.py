import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.tao_anh_ai.service import LocalImageService

svc = LocalImageService('dummy-model', ROOT / '_verify_model_cache')
positive, negative = svc.build_prompt(
    'tạo 1 nữ kiếm hiệp cầm 1 thanh kiếm, toàn thân, ảnh thật',
    'photo',
    'TEXT2IMG',
)

need_positive = [
    'EXACTLY ONE CHARACTER ONLY',
    'female wuxia swordswoman',
    'ONE visible sword in hand',
    'FULL BODY',
    'No wings or angel parts',
]
need_negative = [
    'missing sword',
    'close-up portrait',
    'wings',
    '3D render',
]

missing = [p for p in need_positive if p not in positive] + [n for n in need_negative if n not in negative]
if missing:
    print('VERIFY FAIL')
    print('POSITIVE:', positive)
    print('NEGATIVE:', negative)
    print('MISSING:', missing)
    raise SystemExit(1)

print('TAO_ANH_AI_V6_5_2_VERIFY: PASS')
print('POSITIVE:', positive)
print('NEGATIVE_OK: yes')
