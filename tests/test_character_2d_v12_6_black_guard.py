from types import SimpleNamespace

from PIL import Image

from app.modules.nhan_vat_2d.image_runtime import _result_was_safety_blocked
from app.modules.nhan_vat_2d.output_guard import inspect_image


def test_safety_flag_detected():
    assert _result_was_safety_blocked(SimpleNamespace(nsfw_content_detected=[True])) is True
    assert _result_was_safety_blocked(SimpleNamespace(nsfw_content_detected=[False])) is False


def test_dark_edges_are_rejected(tmp_path):
    p = tmp_path / "edge.png"
    im = Image.new("RGB", (256, 256), (0, 0, 0))
    for x in range(40, 216):
        for y in range(40, 216):
            im.putpixel((x, y), (230, 230, 230))
    im.save(p)
    r = inspect_image(p)
    assert r["ok"] is False
    assert "dark_background_edges" in r["issues"]
