from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.prompt_contract import fit_prompt_to_pipeline
from app.modules.tao_anh_ai.service import LocalImageService


class _Translator:
    MAP = {
        'tạo con mèo trắng nằm trên ghế đỏ': 'create a white cat lying on a red chair',
        'tạo 2 robot màu bạc đứng trong nhà máy ban đêm': 'create two silver robots standing in a factory at night',
        'tạo xe thể thao đỏ dưới mưa': 'create a red sports car in the rain',
        'tạo máy bay trực thăng bay trên núi lúc hoàng hôn': 'create a helicopter flying over mountains at sunset',
        'tạo bản đồ đảo có núi lửa và sông': 'create an island map with a volcano and a river',
        'tạo 1 nữ kiếm hiệp cầm 1 thanh kiếm, toàn thân, ảnh thật': 'create a female wuxia swordswoman holding one sword full body photorealistic',
    }
    def translate_to_english(self, text):
        return self.MAP.get(text, text)


class _Encoded:
    def __init__(self, input_ids):
        self.input_ids = input_ids


class _Clip77Tokenizer:
    model_max_length = 77
    def __call__(self, text, truncation=False, add_special_tokens=True, verbose=False):
        pieces = re.findall(r"[A-Za-z0-9]+|[^\w\s]", text)
        count = 2 + int(len(pieces) * 1.15)
        return _Encoded(list(range(count)))


class _Pipe:
    def __init__(self):
        self.tokenizer = _Clip77Tokenizer()
        self.tokenizer_2 = _Clip77Tokenizer()


svc = LocalImageService('dummy-model', ROOT / '_verify_model_cache')
svc._translator = _Translator()
pipe = _Pipe()

# 1) Generic prompts must preserve their own semantics and must not inject the
# hard-coded swordswoman package unless the user asked for it.
generic_cases = [
    ('tạo con mèo trắng nằm trên ghế đỏ', ('cat', 'red chair'), ('sword', 'wuxia swordswoman')),
    ('tạo 2 robot màu bạc đứng trong nhà máy ban đêm', ('two silver robots', 'factory', 'night'), ('sword', 'female wuxia')),
    ('tạo xe thể thao đỏ dưới mưa', ('red sports car', 'rain'), ('sword', 'archer')),
    ('tạo máy bay trực thăng bay trên núi lúc hoàng hôn', ('helicopter', 'mountains', 'sunset'), ('sword', 'full body standing')),
    ('tạo bản đồ đảo có núi lửa và sông', ('island map', 'volcano', 'river'), ('swordswoman', 'one person only')),
]
for prompt, required, forbidden in generic_cases:
    positive, negative = svc.build_prompt(prompt, 'photo', 'TEXT2IMG')
    fit = fit_prompt_to_pipeline(positive, pipe)
    missing = [item for item in required if item not in fit.text]
    if missing:
        raise SystemExit(f'VERIFY FAIL - missing generic semantics for {prompt}: {missing} | got={fit.text}')
    leaked = [item for item in forbidden if item in fit.text]
    if leaked:
        raise SystemExit(f'VERIFY FAIL - leaked hard-coded character defaults for {prompt}: {leaked} | got={fit.text}')
    if fit.truncated:
        raise SystemExit(f'VERIFY FAIL - generic prompt still truncates for {prompt}: {fit.as_dict()}')

# 2) Character prompt still keeps the hard constraints when the user truly asks.
char_prompt = 'tạo 1 nữ kiếm hiệp cầm 1 thanh kiếm, toàn thân, ảnh thật'
positive, negative = svc.build_prompt(char_prompt, 'photo', 'TEXT2IMG')
fit = fit_prompt_to_pipeline(positive, pipe)
for item in ('one person only', 'holding one visible sword', 'full body standing', 'photorealistic'):
    if item not in fit.text:
        raise SystemExit(f'VERIFY FAIL - character semantics lost: {item} | got={fit.text}')
if fit.truncated:
    raise SystemExit(f'VERIFY FAIL - character prompt still truncates: {fit.as_dict()}')

print('GENERAL_SEMANTIC_PROMPT_V6_5_7_VERIFY: PASS')
