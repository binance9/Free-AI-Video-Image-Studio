from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .character_visual_qa import CharacterVisualQA, VIEW_ORDER
from .service import Local3DService
from .workspace import Model3DWorkspace


class FakeVision:
    def __init__(self, payload=None, available=True):
        self.payload = payload
        self.available = available

    def vision_status(self):
        return {"available": self.available, "model": "fake-vision" if self.available else None}

    def analyze_image(self, _path, _request):
        if not self.available:
            return {"available": False, "summary": None, "note": "missing"}
        return {"available": True, "summary": json.dumps(self.payload)}


def _renders(tmp_path):
    result = {}
    for view in VIEW_ORDER:
        path = tmp_path / f"{view}.png"
        Image.new("RGB", (64, 64), "green").save(path)
        result[view] = str(path)
    return result


def test_visual_evaluator_requires_all_views_and_real_json(tmp_path):
    payload = {"face_pass": True, "eyes_pass": True, "mouth_pass": True, "body_pass": True,
               "score": 91, "face_evidence": "clear", "eyes_evidence": "balanced",
               "mouth_evidence": "neutral", "body_evidence": "balanced", "texture_evidence": "clean"}
    result = CharacterVisualQA(FakeVision(payload)).evaluate(_renders(tmp_path), tmp_path)
    assert result["status"] == "PASS" and result["score"] == 91
    assert Path(result["montage"]).is_file()


def test_visual_evaluator_does_not_fake_when_unsupported(tmp_path):
    result = CharacterVisualQA(FakeVision(available=False)).evaluate(_renders(tmp_path), tmp_path)
    assert result["status"] == "UNSUPPORTED" and result["pass"] is False and result["score"] is None


class FakeBackend:
    def __init__(self, root):
        self.root = Path(root)
        self.calls = 0

    def generate(self, _image, output_dir, **_kwargs):
        self.calls += 1
        output = Path(output_dir) / "character.glb"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"candidate")
        return {"model_path": output, "backend": "fake"}


def _service(tmp_path, statuses, backend="character_hd"):
    service = object.__new__(Local3DService)
    service.root = tmp_path
    service.character_hd = FakeBackend(tmp_path)
    service.triposr = FakeBackend(tmp_path)
    service._validate_image = lambda _path: None
    service._normalize_generated_character = lambda result, _backend, _progress=None: {
        **result, "normalization": {"geometry_pass": True, "ground_pass": True,
                                    "pivot_center_pass": True, "export_roundtrip_pass": True}}
    calls = []
    def visual(result, actual_backend, _source, attempt, _progress=None):
        status = statuses[min(attempt - 1, len(statuses) - 1)]
        calls.append(attempt)
        return {**result, "visual_qa": {"status": status, "score": 90 - attempt},
                "ready_for_rig": actual_backend == "character_hd" and status == "PASS",
                "quality_stage": "FINAL" if actual_backend == "character_hd" and status == "PASS" else "DRAFT"}
    service._visual_qa_generated_character = visual
    return service, calls


def test_quick_is_always_draft(tmp_path):
    source = tmp_path / "source.png"; Image.new("RGB", (128, 128), "white").save(source)
    service, _calls = _service(tmp_path, ["PASS"])
    result = service.from_image(source, tmp_path / "quick", backend="quick")
    assert result["quality_stage"] == "DRAFT" and result["ready_for_rig"] is False
    assert result["retry_count"] == 0


def test_hd_visual_pass_is_ready(tmp_path):
    source = tmp_path / "source.png"; Image.new("RGB", (128, 128), "white").save(source)
    service, calls = _service(tmp_path, ["PASS"])
    result = service.from_image(source, tmp_path / "hd", backend="character_hd")
    assert result["ready_for_rig"] is True and result["quality_stage"] == "FINAL"
    assert calls == [1] and result["retry_count"] == 0


def test_hd_fail_retries_at_most_two_and_selects_best(tmp_path):
    source = tmp_path / "source.png"; Image.new("RGB", (128, 128), "white").save(source)
    service, calls = _service(tmp_path, ["FAIL", "FAIL", "FAIL"])
    result = service.from_image(source, tmp_path / "hd", backend="character_hd")
    assert calls == [1, 2, 3]
    assert result["attempt_count"] == 3 and result["retry_count"] == 2
    assert result["selected_candidate"] == 1
    assert result["ready_for_rig"] is False


def test_hd_pass_candidate_beats_higher_scoring_failed_candidate(tmp_path):
    source = tmp_path / "source.png"; Image.new("RGB", (128, 128), "white").save(source)
    service, calls = _service(tmp_path, ["FAIL", "PASS"])
    result = service.from_image(source, tmp_path / "hd", backend="character_hd")
    assert calls == [1, 2] and result["selected_candidate"] == 2
    assert result["ready_for_rig"] is True and result["retry_count"] == 1


def test_hd_unsupported_does_not_retry(tmp_path):
    source = tmp_path / "source.png"; Image.new("RGB", (128, 128), "white").save(source)
    service, calls = _service(tmp_path, ["UNSUPPORTED"])
    result = service.from_image(source, tmp_path / "hd", backend="character_hd")
    assert calls == [1] and result["retry_count"] == 0 and result["ready_for_rig"] is False


def test_workspace_persists_source_and_qa_renders(tmp_path):
    model = tmp_path / "model.glb"; model.write_bytes(b"glb")
    source = tmp_path / "source.png"; Image.new("RGB", (8, 8), "white").save(source)
    renders = _renders(tmp_path)
    montage = tmp_path / "montage.jpg"; Image.new("RGB", (32, 32), "black").save(montage)
    workspace = Model3DWorkspace(tmp_path / "assets")
    payload = workspace.create_asset(model, None, {
        "source_image": str(source), "visual_qa": {"views": renders, "montage": str(montage), "status": "PASS"}
    })
    folder = workspace.root / payload["asset_id"]
    assert (folder / payload["source_image"]).is_file()
    assert set(payload["visual_qa"]["views"]) == set(VIEW_ORDER)
    assert all((folder / path).is_file() for path in payload["visual_qa"]["views"].values())
    assert (folder / payload["visual_qa"]["montage"]).is_file()
