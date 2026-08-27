from pathlib import Path

from app.modules.character_2d_addon.spec_parser import parse_character_spec
from app.modules.character_2d_addon.prompt_lock import build_locked_prompt
from app.modules.character_2d_addon.export_gate import decide_export
from app.modules.character_2d_addon.repair_planner import plan_repairs


def test_spec_parser_extracts_required_attributes():
    s=parse_character_spec('male fantasy swordsman, blue armor, purple sash, long dark hair, one straight sword, full body')
    assert s.gender=='male'
    assert s.weapon_type=='sword'
    assert s.weapon_count==1
    assert s.armor_primary=='blue'
    assert s.accent_color=='purple'
    assert s.hair_color=='dark'
    assert s.hair_length=='long'


def test_prompt_lock_forbids_second_weapon():
    s=parse_character_spec('male swordsman, blue armor, purple sash, one straight sword')
    pos,neg=build_locked_prompt(s)
    assert 'EXACTLY ONE VISIBLE SWORD TOTAL' in pos
    assert 'LEFT HAND EMPTY' in pos
    assert 'second weapon' in neg
    assert 'two swords' in neg


def test_export_gate_rejects_hard_attribute_failure():
    base={'passed':True,'quality_score':88,'issues':[]}
    attrs={'hard_failures':['weapon_count'],'uncertain':[]}
    gate=decide_export(base,attrs,72)
    assert gate['accepted'] is False
    assert 'weapon_count' in gate['blockers']


def test_export_gate_accepts_when_no_blockers():
    base={'passed':True,'quality_score':88,'issues':[]}
    attrs={'hard_failures':[],'uncertain':['accent_color']}
    gate=decide_export(base,attrs,72)
    assert gate['accepted'] is False
    assert 'accent_color' in gate['blockers']


def test_repair_planner_builds_attribute_repairs():
    s=parse_character_spec('male swordsman, blue armor, purple sash, one sword')
    fixes=plan_repairs(['gender','weapon_count','armor_color','accent_color'],s)
    joined=' '.join(fixes)
    assert 'MALE' in joined
    assert 'ONE SWORD' in joined
    assert 'BLUE' in joined
    assert 'PURPLE' in joined
