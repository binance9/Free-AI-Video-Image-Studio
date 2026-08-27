from pathlib import Path

from PIL import Image

from app.modules.character_2d_addon.operation_gate import detect_operation, target_palette_score, build_recolor_gate
from app.modules.character_2d_addon.spec_parser import parse_character_spec


def _solid_character(path: Path, armor=(150,24,38), accent=(205,150,34)):
    im = Image.new('RGB', (512,512), (235,235,235))
    # simple body blocks large enough to make target colors measurable
    for x in range(170,342):
        for y in range(120,400):
            im.putpixel((x,y), armor)
    for x in range(210,302):
        for y in range(230,270):
            im.putpixel((x,y), accent)
    im.save(path)


def test_detect_recolor_beats_preserve_words():
    p='keep the same female elf, same face, change the armor colors to burgundy red and gold, change the cape to dark red'
    assert detect_operation(p) == 'recolor-reference'


def test_detect_preserve_refine():
    assert detect_operation('clean and refine the reference, same design, same colors, improve sharpness') == 'preserve-refine'


def test_target_palette_red_gold_scores_high(tmp_path):
    p=tmp_path/'red.png'; _solid_character(p)
    spec=parse_character_spec('female elf, change armor colors to burgundy red and gold, change cape to dark red')
    score=target_palette_score(p,spec)
    assert score['score'] >= 0.52
    assert score['ok'] is True


def test_recolor_gate_ignores_clip_color_failures_when_palette_passes(tmp_path):
    p=tmp_path/'red.png'; _solid_character(p)
    spec=parse_character_spec('female elf archer, one bow, change armor colors to burgundy red and gold, change cape to dark red')
    palette=target_palette_score(p,spec)
    validation={
        'base': {'quality_score': 85, 'issues': [], 'passed': True},
        'attributes': {
            'checks': [
                {'check':'gender','ok':True}, {'check':'weapon_type','ok':True}, {'check':'weapon_count','ok':True},
                {'check':'armor_color','ok':False}, {'check':'accent_color','ok':False}, {'check':'cape_color','ok':False},
                {'check':'single_character','ok':True}, {'check':'compact_proportions','ok':True},
            ],
            'hard_failures':['armor_color','accent_color','cape_color'], 'uncertain':[]
        }
    }
    sim={'ok':True,'similarity':0.82,'threshold':0.54}
    gate=build_recolor_gate(validation,sim,palette,70)
    assert gate['accepted'] is True
    assert 'armor_color' not in gate['blockers']
    assert gate['gate_debug']['ignored_original_color_similarity'] is True


def test_missing_clip_similarity_is_not_zero_identity_failure(tmp_path):
    p=tmp_path/'red2.png'; _solid_character(p)
    spec=parse_character_spec('female elf archer, one bow, change armor colors to burgundy red and gold, change cape to dark red')
    palette=target_palette_score(p,spec)
    validation={
        'base': {'quality_score': 85, 'issues': [], 'passed': True},
        'attributes': {
            'checks': [
                {'check':'gender','ok':True}, {'check':'weapon_type','ok':True}, {'check':'weapon_count','ok':True},
                {'check':'single_character','ok':True}, {'check':'compact_proportions','ok':True},
            ],
            'hard_failures':[], 'uncertain':[]
        }
    }
    sim={'ok':None,'similarity':None,'threshold':0.54,'error':'validator unavailable'}
    gate=build_recolor_gate(validation,sim,palette,70)
    assert gate['gate_debug']['identity_similarity'] > 0.0
    assert 'reference_identity_drift' not in gate['blockers']


def test_create_based_on_reference_without_change_is_preserve():
    p='create a compact female chibi elf archer based on the reference, blonde ponytail, pointed elf ears, one bow, one quiver, full body'
    assert detect_operation(p) == 'preserve-refine'
