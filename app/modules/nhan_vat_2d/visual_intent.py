from __future__ import annotations

import json

from app.modules.ga_brain.model_client import OllamaClient

# Deterministic spec_parser.py only catches explicit hard facts stated in exact
# words (gender/weapon/color/hair) via keyword matching. It has no way to
# translate vague aesthetic language ("đẹp", "sang", "tiên hiệp", "thanh
# thoát") into anything a diffusion prompt can act on - those words just sit
# unused in the raw_prompt tail today. This module is the missing semantic
# layer: an LLM call that turns vague visual intent into concrete, renderable
# descriptor phrases, without ever overriding what spec_parser already
# determined from explicit words, and without forcing a beauty preset onto a
# character type it doesn't fit (chibi/monster/child/elderly/muscular/etc).

VISUAL_INTENT_SYSTEM = """
Mày là bộ phiên dịch ý đồ hình ảnh cho hệ tạo nhân vật game. Owner nói bằng
ngôn ngữ đời thường (Việt/Anh lẫn lộn) - việc của mày là dịch những từ mơ hồ
("đẹp", "xinh", "sang", "premium", "thanh thoát", "tiên hiệp", "như game 3D")
thành các cụm mô tả kỹ thuật CỤ THỂ, RENDER ĐƯỢC (tiếng Anh, dùng được thẳng
trong prompt vẽ ảnh) - không giữ nguyên từ mơ hồ đó trong output.

TUYỆT ĐỐI KHÔNG tự áp preset "nữ đẹp mảnh mai" nếu owner đang mô tả: chibi,
lùn/dwarf, quái vật/monster, trẻ em, người già, chiến binh cơ bắp, hoặc bất
kỳ kiểu dáng nào rõ ràng KHÔNG phải "thanh mảnh xinh đẹp". Khi đó để trống
các field liên quan, không suy diễn.

Nếu owner dùng các từ như "giữ nguyên", "chỉ", "thôi", "đừng đổi" - đây là
YÊU CẦU SỬA (patch) một nhân vật đã có, không phải tạo mới. Set is_patch=true
và chỉ điền field owner thực sự nhắc tới; field khác để trống (không suy diễn
đổi thêm thứ owner không nói).

Trả đúng JSON, mỗi field là 1 list các cụm mô tả tiếng Anh ngắn (rỗng nếu
owner không có ý đó hoặc không phù hợp):
{
 "is_patch": false,
 "beauty_priority": false,
 "face_beauty": [],
 "body_style": [],
 "hair_style": [],
 "costume_style": [],
 "pose_style": [],
 "camera_style": [],
 "lighting_style": [],
 "render_style": [],
 "preserve": []
}
"preserve" liệt kê đúng những phần owner bảo giữ nguyên (vd "face","hair","costume","identity").
"""

# Applied only when the interpreter itself flags beauty_priority=true AND the
# request is female-presenting AND nothing above already populated a
# conflicting body/face direction - never blindly, per spec_parser's own
# existing gender field (never overridden here, only read).
FEMALE_FANTASY_BEAUTY_V1 = {
    "face_beauty": ["delicate youthful facial features", "soft V-shaped jawline", "smooth cheeks",
                     "bright expressive eyes", "small refined nose", "balanced elegant lips"],
    "body_style": ["graceful slim proportions", "relatively small refined head", "long elegant legs",
                    "narrow refined shoulders", "smooth waist-to-hip transition"],
    "hair_style": ["voluminous face-framing hair", "layered flowing hair"],
    "render_style": ["premium polished game character presentation", "smooth polished skin shading"],
    "lighting_style": ["soft cinematic key and fill lighting", "subtle rim separation"],
    "camera_style": ["flattering perspective", "avoid exaggerated wide-angle distortion"],
}

MALE_HERO_V1 = {
    "face_beauty": ["clear defined jawline", "readable facial structure"],
    "body_style": ["heroic athletic proportions", "balanced shoulders"],
    "render_style": ["premium fantasy game presentation", "strong appealing lighting"],
}

BEAUTY_NEGATIVE = (
    "oversized head, short legs, bulky anatomy, malformed anatomy, asymmetrical eyes, crossed eyes, "
    "warped face, harsh aged facial features, muddy skin, waxy plastic skin, stiff mannequin pose, "
    "distorted perspective, extreme wide-angle, low-detail eyes"
)

_OFF_PRESET_MARKERS = ("chibi", "dwarf", "monster", "quái vật", "lùn", "trẻ em", "child", "elderly",
                        "già", "cơ bắp", "muscular", "warrior", "béo", "fat")

# Deterministic backstop (same idea as spec_parser.py's VI_GENDER/VI_WEAPONS):
# real testing (2026-08-29) showed the LLM call is not reliable run-to-run -
# the exact same message sometimes returns rich descriptors, sometimes
# returns everything empty including beauty_priority itself. A keyword hit
# here always forces beauty_priority=True regardless of what the LLM
# answered, so apply_beauty_preset's generic preset still fires as a
# reliable floor even on a run where the LLM call produced nothing useful.
BEAUTY_TRIGGER_WORDS = ("đẹp", "xinh", "sang", "xịn", "chuẩn", "thanh thoát", "thanh mảnh",
                         "premium", "beautiful", "elegant", "polished", "gorgeous", "pretty")

CHARACTER_IMAGE_DEBUG = False


def _log(*parts):
    if CHARACTER_IMAGE_DEBUG:
        print("[visual_intent]", *parts)


class VisualIntentInterpreter:
    """Thin, reusable wrapper - no character-module-specific state, so the
    same instance can enrich nhan_vat_2d, nhan_vat_3d's concept-image step,
    or any other character-shaped image prompt without duplicating the LLM
    calling code (mirrors the pattern already proven in ga_brain/self_heal)."""

    def __init__(self, model_client: OllamaClient | None = None):
        self.model = model_client or OllamaClient()

    def interpret(self, message: str, existing_spec: dict | None = None) -> dict:
        empty = {"is_patch": False, "beauty_priority": False, "face_beauty": [], "body_style": [],
                 "hair_style": [], "costume_style": [], "pose_style": [], "camera_style": [],
                 "lighting_style": [], "render_style": [], "preserve": []}
        text = str(message or "").strip()
        low = text.lower()
        keyword_beauty = any(w in low for w in BEAUTY_TRIGGER_WORDS)
        if len(text) < 2:
            return empty
        packet = {"owner_message": text, "existing_character_spec": existing_spec or None}
        messages = [
            {"role": "system", "content": VISUAL_INTENT_SYSTEM},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
        ]
        out = dict(empty)
        try:
            obj = self.model.json(messages, fast=False, deep=True)
        except Exception as exc:
            _log("LLM call failed:", exc)
            obj = None
        if isinstance(obj, dict):
            for key in out:
                if key in ("is_patch", "beauty_priority"):
                    out[key] = bool(obj.get(key))
                else:
                    val = obj.get(key)
                    out[key] = [str(x) for x in val if str(x).strip()] if isinstance(val, list) else []
        # Real-world observation (2026-08-29): the LLM call is not reliable
        # run-to-run for the exact same message - sometimes rich content with
        # beauty_priority still literally false, sometimes everything empty
        # including the flag. Never trust its own summary flag alone (same
        # "verify from real data" rule this codebase applies everywhere
        # else): derive from whatever descriptors it DID produce, OR fall
        # back to the deterministic keyword list so a bad/failed LLM call
        # never silently drops the feature entirely.
        style_keys = ("face_beauty", "body_style", "hair_style", "costume_style",
                      "pose_style", "camera_style", "lighting_style", "render_style")
        if keyword_beauty or any(out[k] for k in style_keys):
            out["beauty_priority"] = True
        _log("resolved intent:", out, "keyword_beauty=", keyword_beauty)
        return out


def apply_beauty_preset(intent: dict, gender: str | None, raw_prompt: str) -> dict:
    """Section 5/6/29: only ever additive, never forced onto a body type the
    request itself signals is different. Never mutates `intent` in place -
    callers keep the LLM's own explicit fields untouched, this only fills
    gaps the interpreter left empty when a preset genuinely applies.

    Respects intent["preserve"] itself (not just left to callers to filter
    afterward) - every current and future caller gets this for free instead
    of each needing to remember to re-apply the same filter."""
    low = raw_prompt.lower()
    if any(marker in low for marker in _OFF_PRESET_MARKERS):
        return intent
    if not intent.get("beauty_priority"):
        return intent
    preset = FEMALE_FANTASY_BEAUTY_V1 if gender == "female" else (MALE_HERO_V1 if gender == "male" else None)
    if preset is None:
        return intent
    preserve = set(str(x).lower() for x in (intent.get("preserve") or []))
    field_to_preserve_key = {"face_beauty": "face", "body_style": "body", "hair_style": "hair",
                              "costume_style": "costume"}
    merged = dict(intent)
    for key, values in preset.items():
        if field_to_preserve_key.get(key) in preserve:
            continue
        if not merged.get(key):
            merged[key] = list(values)
    return merged
