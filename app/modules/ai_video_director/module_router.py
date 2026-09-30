from __future__ import annotations
from dataclasses import dataclass, asdict
import re
from typing import Any

class AmbiguousTaskError(ValueError):
    pass

@dataclass(frozen=True)
class ModuleRoute:
    task_type: str
    module: str
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

MODULE_CONTRACTS = {
    "tao_anh_ai": {
        "owns": ["ai_image_generation", "image_reference_edit"],
        "forbidden": ["2d_character_pipeline", "3d_character", "3d_object", "video_generation"],
    },
    "nhan_vat_2d": {
        "owns": ["2d_character"],
        "forbidden": ["3d_character", "3d_object", "video_generation"],
    },
    "nhan_vat_3d": {
        "owns": ["3d_character"],
        "forbidden": ["3d_object", "generic_prop", "environment_asset"],
    },
    "do_vat_3d": {
        "owns": ["3d_object", "generic_prop", "environment_asset"],
        "forbidden": ["3d_character", "face_body_character_qa"],
    },
    "tao_video_ai": {
        "owns": ["ai_video_generation"],
        "forbidden": ["image_generation", "3d_generation", "video_editing"],
    },
    "chinh_sua_video": {
        "owns": ["video_editing", "assembly", "final_render"],
        "forbidden": ["ai_video_generation", "image_generation", "3d_generation"],
    },
    "phu_de": {"owns": ["subtitles"], "forbidden": ["image_generation", "video_generation"]},
    "am_nhac": {"owns": ["music"], "forbidden": ["image_generation", "video_generation"]},
    "ga_maintenance": {"owns": ["system_check", "safe_cleanup"], "forbidden": ["creative_generation"]},
}

_CHARACTER_WORDS = {
    "nhân vật","nhan vat","người","nguoi","cô gái","co gai","nữ","nu","nam","cung thủ","cung thu",
    "kiếm sĩ","kiem si","warrior","archer","hero","heroine","character","person","woman","girl","man","boy","human","npc"
}
_OBJECT_WORDS = {
    "bụi hoa","bui hoa","bụi cây","bui cay","hoa","cây","cay","cỏ","co","đá","da","rương","ruong","thùng","thung",
    "ghế","ghe","bàn","ban","kiếm","kiem","cung","vũ khí","vu khi","nhà","nha","cột","cot","đèn","den",
    "hàng rào","hang rao","prop","object","asset","bush","flower","tree","rock","chest","barrel","chair","table",
    "weapon","sword","bow","building","fence","lamp","environment"
}

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _contains_any(text: str, words: set[str]) -> bool:
    return any(w in text for w in words)

def route_task(text: str, *, requested_output: str | None = None, explicit_module: str | None = None) -> ModuleRoute:
    t = _norm(text)
    out = _norm(requested_output or "")

    if explicit_module:
        m = explicit_module.strip()
        if m not in MODULE_CONTRACTS:
            raise AmbiguousTaskError(f"UNKNOWN_MODULE: {m}")
        return ModuleRoute("explicit", m, 1.0, "explicit_module")

    if any(x in t for x in ("dọn rác","don rac","kiểm tra máy","kiem tra may","cuda","vram")):
        return ModuleRoute("system_maintenance", "ga_maintenance", 0.99, "maintenance keywords")
    if any(x in t for x in ("phụ đề","phu de","subtitle")):
        return ModuleRoute("subtitles", "phu_de", 0.99, "subtitle request")
    if any(x in t for x in ("âm nhạc","am nhac","nhạc","music")):
        return ModuleRoute("music", "am_nhac", 0.99, "music request")
    if any(x in out for x in ("video edit","edit video","chỉnh sửa video","chinh sua video")):
        return ModuleRoute("video_editing", "chinh_sua_video", 1.0, "requested_output")
    if any(x in out for x in ("video","mp4")):
        return ModuleRoute("ai_video_generation", "tao_video_ai", 1.0, "requested_output")

    is_char = _contains_any(t, _CHARACTER_WORDS)
    is_obj = _contains_any(t, _OBJECT_WORDS)

    if any(x in out for x in ("3d","glb","gltf")) or any(x in t for x in (" 3d","3d ","glb","gltf")):
        if is_char and is_obj:
            primary_char = ("nhân vật","nhan vat","character","người","nguoi","cô gái","co gai","warrior","archer")
            if any(x in t for x in primary_char):
                return ModuleRoute("3d_character", "nhan_vat_3d", 0.95, "character primary; object accessory")
            raise AmbiguousTaskError("AMBIGUOUS_3D_TASK: có cả dấu hiệu nhân vật và đồ vật")
        if is_char:
            return ModuleRoute("3d_character", "nhan_vat_3d", 0.99, "3D character keywords")
        if is_obj:
            return ModuleRoute("3d_object", "do_vat_3d", 0.99, "3D object/prop keywords")
        raise AmbiguousTaskError("AMBIGUOUS_3D_TASK: chưa xác định là nhân vật hay đồ vật")

    if any(x in out for x in ("2d","sprite")) or any(x in t for x in (" 2d","2d ","sprite")):
        if is_char:
            return ModuleRoute("2d_character", "nhan_vat_2d", 0.99, "2D character keywords")
        raise AmbiguousTaskError("AMBIGUOUS_2D_TASK: nhan_vat_2d chỉ nhận nhân vật 2D")

    if any(x in out for x in ("image","png","jpg","ảnh","anh")):
        return ModuleRoute("ai_image_generation", "tao_anh_ai", 1.0, "requested_output")
    if any(x in t for x in ("tạo video","tao video","generate video")):
        return ModuleRoute("ai_video_generation", "tao_video_ai", 0.99, "video request")
    if any(x in t for x in ("tạo ảnh","tao anh","generate image")):
        return ModuleRoute("ai_image_generation", "tao_anh_ai", 0.99, "image request")

    raise AmbiguousTaskError("AMBIGUOUS_TASK: không đủ dữ liệu để chọn đúng một module")
