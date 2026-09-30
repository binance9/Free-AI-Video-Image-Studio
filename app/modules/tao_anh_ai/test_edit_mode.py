import io
import sys
from types import SimpleNamespace

from PIL import Image

from .service import DREAMSHAPER_MODEL, SDXL_MODEL, LocalImageService, generation_mode


class Translator:
    def translate_to_english(self, text):
        if "dựa theo" in text:
            return "based on this image create a character holding a sword"
        return "create a female character holding a sword"


def service(tmp_path):
    result = LocalImageService("unused", tmp_path / "models")
    result._translator = Translator()
    return result


def test_1_no_image_photo_routes_text2img_with_realistic_constraints(tmp_path):
    assert generation_mode(has_image=False, prompt="tạo nhân vật nữ cầm kiếm phong cách ảnh thật") == "TEXT2IMG"
    positive, negative = service(tmp_path).build_prompt("tạo nhân vật nữ cầm kiếm phong cách ảnh thật", "photo", "TEXT2IMG")
    assert "photoreal" in positive.lower()
    assert "real-person proportions" in positive.lower()
    assert "no chibi" in ("no " + negative.lower().replace(", ", ", no "))


def test_2_upload_sword_edit_uses_image_payload_and_preserve_prompt(tmp_path):
    prompt = "cho nhân vật cầm kiếm"
    assert generation_mode(has_image=True, prompt=prompt) == "IMAGE_EDIT"
    positive, negative = service(tmp_path).build_prompt(prompt, "photo", "IMAGE_EDIT")
    assert "preserve the original character identity" in positive
    assert "only add or replace the weapon with one sword" in positive
    for blocked in ("redesign", "face distortion", "anatomy deformation", "extra limbs",
                    "costume replacement", "style drift", "floating weapon", "hand deformation"):
        assert blocked in negative

    source = tmp_path / "character.png"
    Image.new("RGB", (32, 32), "red").save(source)
    captured = {}
    class Pipe:
        def __call__(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(images=[kwargs["image"]])
    item = service(tmp_path)
    item._img_pipe = Pipe()
    item.edit(source, prompt, size="1024x1024")
    assert captured["image"].getpixel((256, 256)) == (255, 0, 0)
    assert captured["strength"] <= 0.28


def test_3_upload_based_on_image_routes_reference_without_chibi(tmp_path):
    prompt = "dựa theo ảnh này tạo nhân vật cầm kiếm"
    assert generation_mode(has_image=True, prompt=prompt) == "IMAGE_REFERENCE"
    positive, negative = service(tmp_path).build_prompt(prompt, "photo", "IMAGE_REFERENCE")
    assert "uploaded image as the dominant reference" in positive
    assert "chibi" in negative


def test_4_photo_positive_and_negative_block_cartoon(tmp_path):
    positive, negative = service(tmp_path).build_prompt("a woman holding a sword", "Ảnh thật", "TEXT2IMG")
    assert "photoreal" in positive.lower() and "realistic" in positive.lower()
    assert "chibi" in negative and "cartoon" in negative


def test_photo_quality_gate_rejects_flat_white_cartoon_layout(tmp_path):
    image = Image.new("RGB", (96, 96), "white")
    for x in range(30, 66):
        for y in range(15, 82):
            image.putpixel((x, y), (20, 120, 30) if (x + y) % 3 else (10, 10, 10))
    assert service(tmp_path)._looks_cartoon(image)


def test_prompts_fit_sd15_clip_window(tmp_path):
    item = service(tmp_path)
    for mode, prompt in (("TEXT2IMG", "tạo nhân vật nữ cầm kiếm phong cách ảnh thật"),
                         ("IMAGE_EDIT", "cho nhân vật cầm kiếm"),
                         ("IMAGE_REFERENCE", "dựa theo ảnh này tạo nhân vật cầm kiếm")):
        positive, _negative = item.build_prompt(prompt, "photo", mode)
        assert len(positive.split()) <= 70


def test_mask_composite_keeps_pixels_outside_selected_region(tmp_path):
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (32, 32), "red").save(source)
    mask_image = Image.new("L", (32, 32), 0)
    for x in range(8, 24):
        for y in range(8, 24):
            mask_image.putpixel((x, y), 255)
    mask_image.save(mask)
    class Pipe:
        def __call__(self, **kwargs):
            return SimpleNamespace(images=[Image.new("RGB", kwargs["image"].size, "blue")])
    item = service(tmp_path)
    item._inpaint_pipe = Pipe()
    data = item.edit(source, "add a sword", size="1024x1024", mask_path=mask)
    output = Image.open(io.BytesIO(data)).convert("RGB")
    assert output.getpixel((50, 50)) == (255, 0, 0)
    assert output.getpixel((512, 512)) == (0, 0, 255)


def test_first_img2img_pipeline_load_returns_callable(tmp_path, monkeypatch):
    class FakePipe:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs): return cls()
        def to(self, _device): return self
        def enable_attention_slicing(self): return None
        def __call__(self, **_kwargs): return None
    fake = SimpleNamespace(AutoPipelineForImage2Image=FakePipe, AutoPipelineForInpainting=FakePipe, AutoPipelineForText2Image=FakePipe)
    monkeypatch.setitem(sys.modules, "diffusers", fake)
    item = service(tmp_path)
    item._runtime = lambda: (None, "cpu", "float32")
    assert callable(item._image_pipeline())


def test_style_and_mode_model_routing_uses_specialized_cached_models(tmp_path, monkeypatch):
    item = service(tmp_path)
    monkeypatch.setattr(item, "_model_is_cached", lambda _model: True)
    assert item._select_model("text", "photo", "create a woman") == SDXL_MODEL
    assert item._select_model("text", "fantasy", "female archer") == SDXL_MODEL
    assert item._select_model("image", "photo", "add a sword") == DREAMSHAPER_MODEL
    assert item._select_model("image", "photo", "add a sword", backend="sd15") == item.model_id


def test_edit_strength_policy_is_intent_sensitive():
    minor = LocalImageService._strength_policy("add a sword", "IMAGE_EDIT", False)
    moderate = LocalImageService._strength_policy("change the entire costume", "IMAGE_EDIT", False)
    redesign = LocalImageService._strength_policy("redesign completely", "IMAGE_EDIT", False)
    reference = LocalImageService._strength_policy("based on this image", "IMAGE_REFERENCE", False)
    assert reference[1] < minor[1] < moderate[1] < redesign[1]
