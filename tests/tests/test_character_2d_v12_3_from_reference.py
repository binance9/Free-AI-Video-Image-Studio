from pathlib import Path
from PIL import Image
import io

from app.modules.character_2d_addon.from_reference import normalize_reference_bytes
from app.modules.character_2d_addon.spec_parser import parse_character_spec
from app.modules.character_2d_addon.prompt_lock import build_locked_prompt


def _png_bytes(size=(400, 800)):
    im = Image.new('RGB', size, (10, 180, 80))
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


def test_reference_normalize_is_square_and_not_cropped(tmp_path):
    out = normalize_reference_bytes(_png_bytes(), 'elf.png', tmp_path/'ref.png', canvas=1024)
    with Image.open(out) as im:
        assert im.size == (1024, 1024)
        # portrait source stays portrait inside padded square; center retains source color
        assert im.getpixel((512,512))[1] > 150
        # outer corner is padding/background
        assert im.getpixel((5,5)) == (232,232,232)


def test_reference_rejects_non_image(tmp_path):
    try:
        normalize_reference_bytes(b'not-an-image', 'x.png', tmp_path/'x.png')
    except ValueError as exc:
        assert 'Invalid reference image' in str(exc)
    else:
        raise AssertionError('invalid bytes should fail')


def test_single_bow_prompt_does_not_force_sword():
    spec = parse_character_spec('female elf archer, green armor, one bow, full body')
    positive, negative = build_locked_prompt(spec)
    assert spec.weapon_type == 'bow'
    assert spec.weapon_count == 1
    assert 'EXACTLY ONE VISIBLE BOW TOTAL' in positive
    assert 'ONE BLADED SWORD ONLY' not in positive
    assert 'sword' in negative.lower()


def test_openapi_has_upload_endpoint():
    from app.api.character_2d_standalone import app
    schema = app.openapi()
    op = schema['paths']['/character-2d/from-reference-simple']['post']
    body = op['requestBody']['content']['multipart/form-data']['schema']
    assert '$ref' in body or body.get('type') == 'object'
