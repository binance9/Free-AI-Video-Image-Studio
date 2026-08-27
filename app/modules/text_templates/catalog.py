"""Curated text and karaoke visual presets; contains styles, never song lyrics."""
from __future__ import annotations

_PRESETS = [
    {"id":"caption_clean","name":"Caption sạch","group":"Chú thích","font_family":"segoe","font_size_ratio":0.050,"color":"#ffffff","outline_color":"#000000","outline_width":4,"background":"#000000","background_opacity":0.28,"shadow_color":"#000000","shadow_opacity":0.55,"shadow_blur":7},
    {"id":"caption_bold","name":"Caption đậm","group":"Chú thích","font_family":"arial","font_size_ratio":0.058,"color":"#ffffff","outline_color":"#101010","outline_width":6,"background":"#000000","background_opacity":0.0,"shadow_color":"#000000","shadow_opacity":0.7,"shadow_blur":8},
    {"id":"karaoke_gold","name":"Karaoke vàng","group":"Lời bài hát","font_family":"segoe","font_size_ratio":0.060,"color":"#ffd54a","outline_color":"#241500","outline_width":6,"background":"#000000","background_opacity":0.15,"shadow_color":"#000000","shadow_opacity":0.75,"shadow_blur":9},
    {"id":"karaoke_neon","name":"Karaoke neon","group":"Lời bài hát","font_family":"segoe","font_size_ratio":0.058,"color":"#72f7ff","outline_color":"#14254a","outline_width":5,"background":"#071018","background_opacity":0.18,"shadow_color":"#4f46e5","shadow_opacity":0.8,"shadow_blur":12},
    {"id":"meme","name":"Meme","group":"Mẫu chữ","font_family":"impact","font_size_ratio":0.070,"color":"#ffffff","outline_color":"#000000","outline_width":7,"background":"#000000","background_opacity":0.0,"shadow_color":"#000000","shadow_opacity":0.4,"shadow_blur":4},
    {"id":"cinematic","name":"Điện ảnh","group":"Mẫu chữ","font_family":"georgia","font_size_ratio":0.052,"color":"#f7ead1","outline_color":"#000000","outline_width":2,"background":"#000000","background_opacity":0.12,"shadow_color":"#000000","shadow_opacity":0.85,"shadow_blur":10},
    {"id":"gaming","name":"Gaming","group":"Mẫu chữ","font_family":"arial","font_size_ratio":0.062,"color":"#a7f3d0","outline_color":"#052e2b","outline_width":6,"background":"#06231f","background_opacity":0.30,"shadow_color":"#22d3ee","shadow_opacity":0.5,"shadow_blur":8},
    {"id":"warning","name":"Nổi bật","group":"Mẫu chữ","font_family":"arial","font_size_ratio":0.062,"color":"#fff4d6","outline_color":"#6b2100","outline_width":6,"background":"#b91c1c","background_opacity":0.45,"shadow_color":"#000000","shadow_opacity":0.65,"shadow_blur":6},
    {"id":"minimal","name":"Tối giản","group":"Mẫu chữ","font_family":"segoe","font_size_ratio":0.046,"color":"#ffffff","outline_color":"#000000","outline_width":1,"background":"#000000","background_opacity":0.0,"shadow_color":"#000000","shadow_opacity":0.35,"shadow_blur":5},
    {"id":"pastel","name":"Pastel","group":"Mẫu chữ","font_family":"segoe","font_size_ratio":0.054,"color":"#ffe4f3","outline_color":"#5b386d","outline_width":4,"background":"#3d2350","background_opacity":0.20,"shadow_color":"#7c3aed","shadow_opacity":0.4,"shadow_blur":8},
]


def list_presets() -> list[dict]:
    return [dict(row) for row in _PRESETS]


def get_preset(preset_id: str) -> dict:
    for row in _PRESETS:
        if row["id"] == preset_id:
            return dict(row)
    raise ValueError("Unknown text preset")
