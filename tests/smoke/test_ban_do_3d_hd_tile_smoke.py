from pathlib import Path
from app.modules.ban_do_3d.cau_hinh_ban_do import resolve_quality
from app.modules.ban_do_3d.dac_ta_ban_do import parse_prompt
from app.modules.ban_do_3d.chia_o_ban_do import build_tiles

def test_quality_contract():
    assert resolve_quality("nhe")[0]=="lite"
    assert resolve_quality("chuan")[0]=="standard"
    assert resolve_quality("dep")[0]=="final"

def test_mapspec_and_tiles():
    q,cfg=resolve_quality("standard")
    spec=parse_prompt("rừng phía tây, thành chính ở trung tâm, sông chạy qua map",q,cfg,8,True)
    assert "rung" in spec.biomes and spec.tile_count==8
    grid=build_tiles(8,spec.tile_size,spec.overlap_px)
    assert len(grid["tiles"])==8
    assert all("neighbors" in x and "world_bbox" in x for x in grid["tiles"])

def test_frontend_files_exist():
    root=Path(__file__).resolve().parents[2]
    assert (root/"web/modules/ban_do_3d/ban_do_3d.js").exists()
    assert (root/"web/modules/ban_do_3d/ban_do_3d.css").exists()
