from pathlib import Path
from PIL import Image
from .quality import image_quality


def test_image_quality_accepts_real_sized_nonflat_image(tmp_path: Path):
    p=tmp_path/'good.png'
    im=Image.new('RGB',(768,768))
    px=im.load()
    for y in range(768):
        for x in range(768):
            v=(x*3+y*5)%256
            px[x,y]=(v,(v*2)%256,(255-v))
    im.save(p)
    qa=image_quality(p)
    assert qa.passed
    assert qa.checks['width']==768


def test_image_quality_rejects_tiny_file(tmp_path: Path):
    p=tmp_path/'bad.png'; p.write_bytes(b'bad')
    qa=image_quality(p)
    assert not qa.passed
