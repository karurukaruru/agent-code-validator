"""Adversarial export checks. Workflow fixtures here are synthetic test data."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

import pytest

from scripts import package_judge_demo as packager
from tests.test_submission_check import checker, update_report, workflow, write


ROOT = Path(__file__).resolve().parents[1]


def sdk_fixture(tmp_path):
    """Copy recorded SDK evidence read-only; mutations below are synthetic."""
    folder = tmp_path / "sdk"
    folder.mkdir()
    original = ROOT / "evidence/upgrade-run/real-sdk/upgrade"
    for name in ("report.json", "manifest.json"):
        (folder / name).write_bytes((original / name).read_bytes())
    return folder


def with_failed_attempt(folder, report):
    record = {"provider": report["provider"], "endpoint": checker.OFFICIAL_API, "status": "FAIL", "http_status": 429,
              "provenance": "live HTTP attempt", "timestamp": "2026-10-25T08:00:00+00:00",
              "parameters": {"model": report["model"]}, "raw_response": "Synthetic rate-limit test fixture"}
    # Keep the original successful proposal and an earlier failed HTTP attempt.
    old = report["requests"][0]
    (folder / "repair-proposal-2.json").write_bytes((folder / "repair-proposal-1.json").read_bytes())
    old.update(name="repair-proposal-2", evidence_file="repair-proposal-2.json")
    write(folder / "repair-proposal-1.json", record)
    report["requests"].insert(0, {"name": "repair-proposal-1", "evidence_file": "repair-proposal-1.json",
                                  "status": "FAIL", "evidence_sha256": checker.digest(record)})
    update_report(folder, report)


def test_failed_attempts_are_preserved_without_inflating_success_count(tmp_path):
    live, report = workflow(tmp_path)
    with_failed_attempt(live, report)
    sdk = sdk_fixture(tmp_path)
    out = tmp_path / "export"
    result = packager.package(live, sdk, out)
    assert "3 hash-bound" in checker.check_runtime(tmp_path, "evidence/workflow/report.json")
    assert (out / "evidence/live/repair-proposal-1.json").read_bytes() == (live / "repair-proposal-1.json").read_bytes()
    assert result["replay_only"] is True
    with zipfile.ZipFile(result["archive"]) as archive:
        assert "evidence/live/repair-proposal-1.json" in archive.namelist()
    manifest = checker.read_json(out / "package-manifest.json")
    assert manifest["new_provider_requests"] == 0


@pytest.mark.parametrize("change", ["version", "source", "output", "contract"])
def test_sdk_headline_cannot_be_reused_with_different_or_forged_evidence(tmp_path, change):
    live, _ = workflow(tmp_path)
    sdk = sdk_fixture(tmp_path)
    report = checker.read_json(sdk / "report.json")
    if change == "version":
        report["cases"][0]["provenance"]["candidate_version"] = "9.9.9"
    elif change == "source":
        report["executions"]["candidate"]["provenance"]["executed_source_sha256"] = "0" * 64
    elif change == "output":
        report["executions"]["candidate"]["output"][0]["content"] = "unrelated"
    else:
        report["cases"][0]["contracts"]["baseline"]["status"] = "PASS"
    write(sdk / "report.json", report)
    write(sdk / "manifest.json", {"run_id": report["run_id"], "report_sha256": checker.digest(report)})
    out = tmp_path / "rejected"
    with pytest.raises(ValueError, match="SDK"):
        packager.package(live, sdk, out)
    assert not out.exists()


def test_export_is_an_allowlist_and_omits_unrelated_local_files(tmp_path):
    live, _ = workflow(tmp_path)
    (live / ".env.local").write_text("DO_NOT_EXPORT", encoding="utf-8")
    (live / "cookies.json").write_text("DO_NOT_EXPORT", encoding="utf-8")
    out = tmp_path / "export"
    packager.package(live, sdk_fixture(tmp_path), out)
    exported = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert not any("cookie" in name or ".env" in name for name in exported)
    assert {"launch_demo.py", "Start-Judge-Demo.cmd", "START-HERE.txt"} <= exported


def test_export_rejects_a_secret_even_if_hashes_are_recomputed(tmp_path):
    live, report = workflow(tmp_path)
    report["unexpected_metadata"] = {"api_key": "synthetic-secret-that-must-not-be-exported"}
    update_report(live, report)
    with pytest.raises(ValueError, match="sensitive field"):
        packager.package(live, sdk_fixture(tmp_path), tmp_path / "rejected")


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://evil.invalid/project", "https://user:pass@github.com/a/b"])
def test_export_rejects_unsafe_source_links(tmp_path, url):
    live, _ = workflow(tmp_path)
    with pytest.raises(ValueError, match="public HTTPS"):
        packager.package(live, sdk_fixture(tmp_path), tmp_path / "rejected", source_url=url)


def test_launcher_serves_only_its_export_folder_from_an_unrelated_cwd(tmp_path):
    live, _ = workflow(tmp_path)
    out = tmp_path / "export"
    packager.package(live, sdk_fixture(tmp_path), out)
    proc = subprocess.Popen([sys.executable, str(out / "launch_demo.py"), "--no-browser"], cwd=tmp_path,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        url = proc.stdout.readline().strip()
        assert url.startswith("http://127.0.0.1:")
        with urllib.request.urlopen(url, timeout=5) as response:
            assert b"PatchCourt" in response.read()
        with urllib.request.urlopen(url + "report.json", timeout=5) as response:
            assert json.load(response)["mode"] == "upgrade-run"
    finally:
        proc.terminate()
        proc.communicate(timeout=5)


def test_package_preserves_existing_archive_and_folder(tmp_path):
    live, _ = workflow(tmp_path)
    sdk = sdk_fixture(tmp_path)
    out = tmp_path / "export"
    archive = tmp_path / "export.zip"
    archive.write_bytes(b"preserve")
    with pytest.raises(ValueError, match="overwrite"):
        packager.package(live, sdk, out)
    assert archive.read_bytes() == b"preserve"
    assert not out.exists()
