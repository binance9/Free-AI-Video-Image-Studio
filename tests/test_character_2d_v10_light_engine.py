from app.modules.character_2d_addon.image_runtime import generation_dimensions, StandaloneLocalImageService, BASE_MODEL


def test_light_engine_defaults():
    assert BASE_MODEL == "Lykon/dreamshaper-8"
    assert StandaloneLocalImageService.engine_name == "dreamshaper-8-fp16"


def test_light_preview_is_small_and_fast():
    w, h = generation_dimensions("1024x1536", "fast")
    assert max(w, h) == 576
    assert min(w, h) >= 512


def test_light_final_internal_size_is_reasonable():
    w, h = generation_dimensions("1024x1536", "high")
    assert max(w, h) == 832
    assert min(w, h) >= 512
