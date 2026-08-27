from pathlib import Path

from app.api.character_2d_standalone import app


def test_health_version_v125():
    health = next(r for r in app.routes if getattr(r, 'path', '') == '/health')
    data = health.endpoint()
    assert data['version'] == '1.3.1'


def test_simple_reference_endpoint_is_compact_in_openapi():
    schema = app.openapi()
    assert '/character-2d/from-reference-simple' in schema['paths']
    assert '/character-2d/from-reference' not in schema['paths']
    op = schema['paths']['/character-2d/from-reference-simple']['post']
    body = op['requestBody']['content']['multipart/form-data']['schema']
    ref = body.get('$ref')
    if ref:
        name = ref.rsplit('/', 1)[-1]
        props = schema['components']['schemas'][name]['properties']
    else:
        props = body['properties']
    assert set(props) == {'image', 'prompt', 'preset', 'strength'}


def test_compact_ui_file_exists_and_has_advanced_collapsed():
    ui = Path(__file__).resolve().parents[2] / 'app' / 'app' / 'web' / 'character_2d' / 'index.html'
    text = ui.read_text(encoding='utf-8')
    assert '<details>' in text
    assert '<summary>Advanced</summary>' in text
    assert 'Generate' in text
    assert '/character-2d/from-reference' in text
