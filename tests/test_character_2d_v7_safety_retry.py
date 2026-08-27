from app.modules.character_2d_addon.image_runtime import image_bytes_are_blank
from PIL import Image
import io


def _png(color):
    im = Image.new("RGB", (64,64), color)
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def test_black_image_detected():
    assert image_bytes_are_blank(_png((0,0,0))) is True


def test_normal_image_not_blank():
    im = Image.new("RGB", (64,64), (120,120,120))
    for x in range(16,48):
        for y in range(16,48):
            im.putpixel((x,y),(200,80,80))
    buf = io.BytesIO(); im.save(buf,"PNG")
    assert image_bytes_are_blank(buf.getvalue()) is False
