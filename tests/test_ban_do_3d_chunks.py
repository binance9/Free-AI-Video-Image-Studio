from __future__ import annotations

import json

from PIL import Image, ImageDraw

from app.modules.ban_do_3d.tach_map_nho import (
    choose_chunk_count,
    rebuild_from_chunks,
    split_master_map,
    validate_chunks,
)
from app.modules.ban_do_3d.cau_hinh_ban_do import resolve_quality
from app.modules.ban_do_3d.chia_o_ban_do import build_tiles
from app.modules.ban_do_3d.dac_ta_ban_do import parse_prompt
from app.modules.ban_do_3d.du_lieu_layout import build_master_layout, enrich_tiles_from_layout
from app.modules.ban_do_3d.tao_o_ban_do import tile_prompt


def test_quality_changes_automatic_chunk_density():
    assert choose_chunk_count(6000, 3000, "lite") < choose_chunk_count(6000, 3000, "standard")
    assert choose_chunk_count(6000, 3000, "standard") < choose_chunk_count(6000, 3000, "final")


def test_split_is_master_crop_and_rebuild_is_pixel_exact(tmp_path):
    master_path = tmp_path / "master.png"
    image = Image.new("RGB", (997, 541), (20, 30, 40))
    draw = ImageDraw.Draw(image)
    draw.line((0, 270, 996, 270), fill=(230, 190, 70), width=11)
    draw.line((500, 0, 500, 540), fill=(40, 150, 230), width=13)
    image.save(master_path)

    chunks_dir = tmp_path / "chunks"
    manifest = split_master_map(
        master_path=master_path, out_dir=chunks_dir, source_map_id="map_test",
        quality="standard", seed=123, biomes=["forest", "coast"],
        constraints=["đường", "sông"],
    )
    rebuild_path = tmp_path / "rebuild.png"
    rebuild_from_chunks(chunks_dir=chunks_dir, manifest=manifest, output_path=rebuild_path)
    validation = validate_chunks(master_path=master_path, rebuilt_path=rebuild_path, manifest=manifest)

    assert validation["pass"] is True
    assert validation["coverage_score"] == 1.0
    assert validation["rebuild_similarity"] == 1.0
    assert validation["neighbors_reciprocal"] is True
    assert validation["feature_coordinates_match"] is True
    assert manifest["generated_from_prompt"] is False
    assert manifest["generated_from_hd_tiles"] is True
    assert manifest["source_of_truth"] is True
    assert 64 <= manifest["overlap"] <= 128
    assert len(manifest["chunks"]) == manifest["chunk_count"]

    for chunk in manifest["chunks"]:
        required = {"chunk_id", "row", "col", "world_x", "world_z", "width", "height", "overlap", "neighbors", "biome", "entry_points", "exit_points"}
        assert required <= chunk.keys()
        chunk_dir = chunks_dir / chunk["chunk_id"]
        assert (chunk_dir / "map.png").is_file()
        assert (chunk_dir / "manifest.json").is_file()
        assert (chunk_dir / "objects.json").is_file()
        objects = json.loads((chunk_dir / "objects.json").read_text())
        assert objects["objects"] == []
        assert {"world_x", "world_y", "world_z", "chunk_id"} <= objects["schema"].keys()
        assert (chunk_dir / "collision.json").is_file()
        assert (chunk_dir / "terrain.json").is_file()


def test_tile_prompt_is_short_terrain_only_and_layout_data_is_not_prompted():
    quality, cfg = resolve_quality("standard")
    spec = parse_prompt("rừng phía tây, sông ở giữa, đường sang biển phía đông", quality, cfg, 8, True).as_dict()
    grid = build_tiles(8, spec["tile_size"], spec["overlap_px"])
    layout = build_master_layout(spec, 3712, 1920)
    enrich_tiles_from_layout(grid, spec, layout)
    prompt = tile_prompt(spec, grid["tiles"][0], None)
    assert len(prompt.split()) <= 77
    assert "No trees" in prompt and "No text" in prompt
    assert "left=" not in prompt and "tile_" not in prompt
    tile = grid["tiles"][0]
    assert {"bbox", "world_x", "world_z", "tile_seed", "master_reference_region", "biome", "road_segments", "river_segments", "coastline_segments"} <= tile.keys()
    assert layout["locked"] is True and layout["terrain_only"] is True
