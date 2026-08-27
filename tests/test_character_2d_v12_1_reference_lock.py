from pathlib import Path

from app.modules.nhan_vat_2d.spec_parser import parse_character_spec
from app.modules.nhan_vat_2d.reference_lock import ReferenceLibrary
from app.modules.nhan_vat_2d.prompt_lock import build_locked_prompt
from app.modules.nhan_vat_2d.export_gate import decide_export


def test_reference_selected_for_compact_male_sword():
    s=parse_character_spec("male swordsman, blue armor, purple sash, one sword")
    s.render_preset="compact_game"
    c=ReferenceLibrary().choose(s)
    assert c.enabled is True
    assert c.key=="compact_male_swordsman"
    assert Path(c.path).is_file()


def test_reference_not_for_unmatched_weapon():
    s=parse_character_spec("female archer, green armor, one bow")
    c=ReferenceLibrary().choose(s)
    assert c.enabled is False


def test_compact_prompt_forbids_pedestal_and_realistic_body():
    s=parse_character_spec("male swordsman, blue armor, purple sash, one sword")
    pos,neg=build_locked_prompt(s)
    assert "HEAD TO BODY RATIO ABOUT ONE TO FOUR" in pos
    assert "NO PEDESTAL" in pos
    assert "pedestal" in neg


def test_gate_rejects_uncertain_reference_critical_checks():
    base={"passed":True,"quality_score":90,"issues":[]}
    attrs={"hard_failures":[],"uncertain":["compact_proportions","no_pedestal"]}
    gate=decide_export(base,attrs,72)
    assert gate["accepted"] is False
    assert "compact_proportions" in gate["blockers"]
    assert "no_pedestal" in gate["blockers"]
