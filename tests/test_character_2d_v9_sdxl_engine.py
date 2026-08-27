from app.modules.nhan_vat_2d.image_runtime import generation_dimensions, StandaloneLocalImageService, BASE_MODEL, LIGHTNING_CKPT


def test_sdxl_engine_defaults():
    assert BASE_MODEL == "stabilityai/stable-diffusion-xl-base-1.0"
    assert LIGHTNING_CKPT == "sdxl_lightning_4step_lora.safetensors"
    assert StandaloneLocalImageService.engine_name == "sdxl-lightning-4step"


def test_sdxl_preview_is_larger_than_old_sd15_preview():
    w, h = generation_dimensions("1024x1536", "fast")
    assert max(w, h) == 768
    assert min(w, h) >= 512


def test_sdxl_final_internal_size_is_larger():
    w, h = generation_dimensions("1024x1536", "high")
    assert max(w, h) == 1152
    assert min(w, h) >= 512
