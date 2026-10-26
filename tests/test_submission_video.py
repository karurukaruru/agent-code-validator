"""Video preparation must preserve provenance and never spend an API request."""
import json
from pathlib import Path
import shutil

import pytest

from patchcourt.evidence import digest, read_json
from scripts.prepare_submission_video import prepare
from scripts.encode_submission_video import encode

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "evidence/development-050/deepseek-live-01/report.json"
SDK = ROOT / "evidence/upgrade-run/real-sdk/upgrade/report.json"


def no_http(*args, **kwargs):
    raise AssertionError("Video preparation attempted a provider request")


def test_prepare_existing_http_evidence_without_new_request(tmp_path, monkeypatch):
    from patchcourt import providers
    monkeypatch.setattr(providers, "request", no_http)
    output = tmp_path / "video"
    result = prepare(LIVE, output, sdk_report=SDK)
    assert result["source_report_sha256"] == digest(read_json(LIVE))
    assert result["source_sdk_report_sha256"] == digest(read_json(SDK))
    assert result["new_inference_during_recording"] is False
    assert result["competition_runtime_source_verified"] is False
    assert (output / "website/sdk/report.json").read_bytes() == SDK.read_bytes()
    assert (output / "website/sdk/manifest.json").read_bytes() == (SDK.parent / "manifest.json").read_bytes()
    assert "RECORDED REPLAY" in (output / "website/index.html").read_text(encoding="utf-8")
    scenes = read_json(output / "narration.json")
    sdk_scene = next(scene for scene in scenes if scene["action"] == "sdk")
    assert "Equal output did not earn a pass" in sdk_scene["text"]
    assert "DeepSeek Flash development run" in scenes[0]["text"]


def test_competition_option_cannot_relabel_deepseek(tmp_path):
    output = tmp_path / "competition"
    with pytest.raises(ValueError, match="NVIDIA model through Nebius"):
        prepare(LIVE, output, competition=True)
    assert not output.exists()


def test_changed_report_cannot_become_a_video(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(LIVE.parent, source)
    report = read_json(source / "report.json")
    report["task"]["answer"]["inventory_value"] = 99
    (source / "report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        prepare(source / "report.json", tmp_path / "video")
    assert not (tmp_path / "video").exists()


def test_rehashed_wrong_sdk_source_is_rejected(tmp_path):
    source = tmp_path / "sdk"
    shutil.copytree(SDK.parent, source)
    report = read_json(source / "report.json")
    report["executions"]["baseline"]["provenance"]["executed_source_sha256"] = "0" * 64
    manifest = read_json(source / "manifest.json")
    manifest["report_sha256"] = digest(report)
    (source / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        prepare(LIVE, tmp_path / "video", sdk_report=source)
    assert not (tmp_path / "video").exists()


def test_preparation_preserves_earlier_cut(tmp_path):
    output = tmp_path / "video"
    output.mkdir()
    (output / "keep.txt").write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh output"):
        prepare(LIVE, output)
    assert (output / "keep.txt").read_text(encoding="utf-8") == "original"


def test_smoke_screenshots_cannot_be_encoded_as_a_complete_video(tmp_path):
    (tmp_path / "capture.json").write_text(json.dumps({
        "status": "SMOKE_VERIFIED", "capture_mode": "recorded-replay-smoke",
        "new_model_requests": 0, "new_search_requests": 0,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="verified offline recorded-replay capture"):
        encode(tmp_path, ffmpeg=tmp_path / "not-executed.exe")
    assert not list(tmp_path.glob("*.mp4"))
