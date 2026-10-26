"""Adversarial export checks. Workflow fixtures here are synthetic test data."""
import json
import hashlib
import stat
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

import pytest

from scripts import package_judge_demo as packager
from tests.test_submission_check import checker, update_report, workflow, write
from tests.test_patchcourt_recording_gate import capture
from patchcourt.recording_export import check_recording, GATE_TEST, PORTABLE_GATE_FILES


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


def captured_gate(tmp_path):
    path, _ = capture(tmp_path)
    output = tmp_path / "captured-gate"
    check_recording(path, output)
    return output


def rehash_gate(folder, *, changed_runtime=False):
    """Synthetic adversary recomputes hashes; only source validation can reject it."""
    report = checker.read_json(folder / "report.json")
    contract = checker.read_json(folder / "contract.json")
    if changed_runtime:
        for name in contract["runtime_files_sha256"]:
            contract["runtime_files_sha256"][name] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        write(folder / "contract.json", contract)
        code = GATE_TEST.replace("CONTRACT_SHA256", hashlib.sha256((folder / "contract.json").read_bytes()).hexdigest())
        (folder / "test_boundary_contract.py").write_text(code, encoding="utf-8")
    gate = report["regression_gate"]
    gate["runtime_files_sha256"] = contract["runtime_files_sha256"]
    gate["contract_file_sha256"] = hashlib.sha256((folder / "contract.json").read_bytes()).hexdigest()
    gate["test_file_sha256"] = hashlib.sha256((folder / "test_boundary_contract.py").read_bytes()).hexdigest()
    with zipfile.ZipFile(folder / "regression-gate.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in PORTABLE_GATE_FILES: archive.write(folder / name, name)
    gate["archive_sha256"] = hashlib.sha256((folder / "regression-gate.zip").read_bytes()).hexdigest()
    update_report(folder, report)


def test_optional_gate_exports_only_the_portable_checked_files_and_truthful_card(tmp_path):
    gate = captured_gate(tmp_path)
    # Discovery can create caches; neither caches nor their contents are shipped.
    cache = gate / "__pycache__"; cache.mkdir(); (cache / "test.pyc").write_bytes(b"untrusted cache")
    live, _ = workflow(tmp_path)
    out = tmp_path / "with-gate"
    packager.package(live, sdk_fixture(tmp_path), out, gate_dir=gate)
    assert {p.relative_to(out / "ci-gate").as_posix() for p in (out / "ci-gate").rglob("*") if p.is_file()} == set(PORTABLE_GATE_FILES)
    assert (out / "ci-gate.zip").read_bytes() == (gate / "regression-gate.zip").read_bytes()
    page = (out / "index.html").read_text(encoding="utf-8")
    assert 'id="ci-gate"' in page and "default test intentionally fails" in page
    assert "does not execute a future SDK" in page
    assert (out / "evidence/ci-gate/report.json").read_bytes() == (gate / "report.json").read_bytes()


def test_rehashed_injected_test_is_rejected_without_execution(tmp_path):
    gate = captured_gate(tmp_path)
    marker = tmp_path / "injected-code-ran.txt"
    with (gate / "test_boundary_contract.py").open("a", encoding="utf-8") as stream:
        stream.write("\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n")
    rehash_gate(gate)
    live, _ = workflow(tmp_path)
    with pytest.raises(ValueError, match="exact reviewed export"):
        packager.package(live, sdk_fixture(tmp_path), tmp_path / "rejected", gate_dir=gate)
    assert not marker.exists() and not (tmp_path / "rejected").exists()


def test_rehashed_alternate_checker_source_is_rejected(tmp_path):
    gate = captured_gate(tmp_path)
    source = gate / "_patchcourt_contract/semantic.py"
    source.write_bytes(source.read_bytes() + b'\ndef compare_messages(*args): return {"status":"PASS","findings":[]}\n')
    rehash_gate(gate, changed_runtime=True)
    with pytest.raises(ValueError, match="current reviewed project source"):
        packager.verify_gate_bundle(gate)


def test_rehashed_green_headline_cannot_replace_observed_broken_data(tmp_path):
    gate = captured_gate(tmp_path)
    report = checker.read_json(gate / "report.json")
    report["status"] = report["cases"][0]["status"] = "PASS"
    report["cases"][0]["findings"] = []
    update_report(gate, report)
    with pytest.raises(ValueError, match="fresh captured-input comparison"):
        packager.verify_gate_bundle(gate)


def test_extra_gate_code_is_not_exported_or_executed(tmp_path):
    gate = captured_gate(tmp_path)
    (gate / "extra.py").write_text("raise RuntimeError('must never execute')", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected file"):
        packager.verify_gate_bundle(gate)


@pytest.mark.parametrize("mutation", ["traversal", "duplicate", "symlink"])
def test_rehashed_archive_path_and_member_attacks_are_rejected(tmp_path, mutation):
    gate = captured_gate(tmp_path)
    archive_path = gate / "regression-gate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name in PORTABLE_GATE_FILES:
            if mutation == "symlink" and name == "contract.json":
                entry = zipfile.ZipInfo(name); entry.create_system = 3; entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, (gate / name).read_bytes())
            else:
                archive.write(gate / name, "../escape.py" if mutation == "traversal" and name == "contract.json" else name)
        if mutation == "duplicate": archive.writestr("contract.json", (gate / "contract.json").read_bytes())
    report = checker.read_json(gate / "report.json")
    report["regression_gate"]["archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    update_report(gate, report)
    with pytest.raises(ValueError, match="Gate archive"):
        packager.verify_gate_bundle(gate)
