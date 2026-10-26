"""Real captured-user-fixture to exported CI gate, with no model or SDK HTTP."""
from copy import deepcopy
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import zipfile

import pytest

from patchcourt.cli import main
from patchcourt.evidence import read_json
from patchcourt.recorder import BoundaryRecorder
from patchcourt.recording import read_recording, select_recording
from patchcourt.recording_export import check_recording


def user_trace():
    # This intentionally differs from PatchCourt's inventory/price demo fixture.
    return [
        {"role": "system", "content": "Quote a courier shipment; preserve the user's units."},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "quote-Z9", "type": "function", "function": {"name": "quote_shipping",
             "arguments": '{"destination":"東京","weight_kg":2.75,"insured":true}'}}]},
        {"role": "tool", "tool_call_id": "quote-Z9", "content": '{"currency":"JPY","amount":1900}'}]


def capture(tmp_path, *, broken=True, name="recording.json", request="quote-1", adapter="courier-adapter", version="1.0"):
    recorder = BoundaryRecorder(adapter, version)
    def convert(messages):
        output = deepcopy(messages)
        if broken:
            output[1].pop("tool_calls")
        return output
    _, verdict = recorder.transform(user_trace(), convert, request_id=request)
    path = tmp_path / name
    recorder.save(path)
    return path, verdict


def run_gate(folder, *, trace=None, recording=None, request=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATCHCOURT_")}
    if trace: env["PATCHCOURT_CANDIDATE_TRACE"] = str(trace)
    if recording: env["PATCHCOURT_CANDIDATE_RECORDING"] = str(recording)
    if request: env["PATCHCOURT_REQUEST_ID"] = request
    return subprocess.run([sys.executable, "-I", str(folder / "test_boundary_contract.py")],
                          cwd=folder.parent, env=env, capture_output=True, text=True, timeout=20)


def test_captured_user_defect_exports_a_red_standalone_gate_then_future_trace_is_green(tmp_path):
    path, observed = capture(tmp_path)
    output = tmp_path / "gate"
    assert observed["status"] == "FAIL"
    assert main(["check-recording", str(path), "--output", str(output)]) == 1
    report = read_json(output / "report.json")
    assert report["status"] == "FAIL"
    assert report["cases"][0]["execution"] is False
    assert report["provider_requests"] == 0
    assert report["regression_gate"]["default_test_expected"] == "FAIL"
    assert report["cases"][0]["baseline"] == user_trace()
    with zipfile.ZipFile(output / "regression-gate.zip") as archive:
        assert set(archive.namelist()) == set(__import__("patchcourt.recording_export", fromlist=["PORTABLE_GATE_FILES"]).PORTABLE_GATE_FILES)
    assert 'name="patchcourt-static-export" content="recording-check"' in (output / "index.html").read_text(encoding="utf-8")
    assert "reproductions" not in (output / "test_boundary_contract.py").read_text(encoding="utf-8")
    failed = run_gate(output)
    assert failed.returncode == 1 and "SEMANTIC_CHANGE" in failed.stderr
    future = tmp_path / "future-trace.json"
    future.write_text(json.dumps(user_trace()), encoding="utf-8")
    passed = run_gate(output, trace=future)
    assert passed.returncode == 0, passed.stderr
    assert "Ran 1 test" in passed.stderr
    assert (output / "_patchcourt_contract/LICENSE").read_bytes() == (Path(__file__).resolve().parents[1] / "LICENSE").read_bytes()


def test_future_real_recording_can_change_version_and_request_id_but_not_input_or_adapter(tmp_path):
    path, _ = capture(tmp_path)
    output = tmp_path / "gate"
    check_recording(path, output)
    future, _ = capture(tmp_path, broken=False, name="future.json", request="quote-2", version="2.0")
    passed = run_gate(output, recording=future)
    assert passed.returncode == 0, passed.stderr
    changed = read_json(future)
    changed["events"][0]["payload"][0]["content"] = "A different task"
    future.write_text(json.dumps(changed), encoding="utf-8")
    failed = run_gate(output, recording=future)
    assert failed.returncode == 1 and "different input contract" in failed.stderr
    different, _ = capture(tmp_path, broken=False, name="other.json", adapter="other-adapter")
    assert "adapter identity differs" in run_gate(output, recording=different).stderr


def test_multiple_transactions_require_selection_and_future_gate_keeps_that_selection(tmp_path):
    recorder = BoundaryRecorder("courier-adapter", "2")
    recorder.transform(user_trace(), deepcopy, request_id="first")
    recorder.transform(user_trace(), deepcopy, request_id="second")
    path = tmp_path / "many.json"; recorder.save(path)
    with pytest.raises(ValueError, match="Select --request-id"):
        check_recording(path, tmp_path / "ambiguous")
    report = check_recording(path, tmp_path / "gate", "second")
    assert report["recording"]["request_id"] == "second"
    assert run_gate(tmp_path / "gate", recording=path, request="second").returncode == 0
    assert run_gate(tmp_path / "gate", recording=path).returncode == 1


@pytest.mark.parametrize("mutation", ["duplicate", "incomplete", "no-id", "bad-id", "bad-time", "reverse-time", "reverse-order", "wrong-shape", "extra-field", "bad-metadata", "bad-flag"])
def test_ambiguous_or_incomplete_recordings_never_export_a_gate(tmp_path, mutation):
    path, _ = capture(tmp_path)
    recording = read_json(path)
    if mutation == "duplicate": recording["events"].append(deepcopy(recording["events"][1]))
    if mutation == "incomplete": recording["events"].pop()
    if mutation == "no-id": recording["events"][0].pop("request_id")
    if mutation == "bad-id": recording["events"][0]["request_id"] = "../escape"
    if mutation == "bad-time": recording["events"][0]["timestamp"] = "2026-10-26T10:00:00"
    if mutation == "reverse-time": recording["events"][0]["timestamp"] = "2099-01-01T00:00:00Z"
    if mutation == "reverse-order": recording["events"].reverse()
    if mutation == "wrong-shape": recording["events"][1]["payload"] = None
    if mutation == "extra-field": recording["events"][0]["model_code"] = "not executed"
    if mutation == "bad-metadata": recording["adapter"] = ""
    if mutation == "bad-flag": recording["events"][0]["payload_redacted"] = 0
    path.write_text(json.dumps(recording), encoding="utf-8")
    with pytest.raises(ValueError): check_recording(path, tmp_path / "gate")
    assert not (tmp_path / "gate").exists()


@pytest.mark.parametrize("raw", ['{"schema_version":"1.0","schema_version":"1.0"}', '{"x":NaN}', '[' * 70 + '0' + ']' * 70])
def test_duplicate_nonfinite_and_excessively_nested_json_are_rejected(tmp_path, raw):
    path = tmp_path / "invalid.json"; path.write_text(raw)
    assert main(["check-recording", str(path), "--output", str(tmp_path / "gate")]) == 2
    assert not (tmp_path / "gate").exists()


def test_redaction_does_not_turn_unequal_original_values_into_a_passing_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_TEST_API_KEY", "local-sensitive-value")
    recorder = BoundaryRecorder("text-adapter", "1")
    recorder.transform([{"role": "user", "content": "local-sensitive-value"}], deepcopy)
    path = tmp_path / "redacted.json"; recorder.save(path)
    report = check_recording(path, tmp_path / "gate")
    assert report["status"] == "INCONCLUSIVE"
    assert report["regression_gate"]["status"] == "BLOCKED"
    assert not (tmp_path / "gate/test_boundary_contract.py").exists()
    assert "local-sensitive-value" not in (tmp_path / "gate/report.json").read_text(encoding="utf-8")


def test_late_credential_loading_before_save_cannot_erase_a_detected_regression(tmp_path, monkeypatch):
    left, right = "SYNTHETIC_INPUT_VALUE_A", "SYNTHETIC_OUTPUT_VALUE_B"
    monkeypatch.delenv("FIRST_API_KEY", raising=False)
    monkeypatch.delenv("SECOND_API_KEY", raising=False)
    recorder = BoundaryRecorder("late-credentials", "1")
    _, verdict = recorder.transform([{"role": "user", "content": left}],
                                    lambda _: [{"role": "user", "content": right}])
    assert verdict["status"] == "FAIL"
    assert all(event["payload_redacted"] is False for event in recorder.events)
    monkeypatch.setenv("FIRST_API_KEY", left)
    monkeypatch.setenv("SECOND_API_KEY", right)
    path = tmp_path / "late.json"; recorder.save(path)
    saved = read_json(path)
    assert all(event["payload_redacted"] is True for event in saved["events"])
    report = check_recording(path, tmp_path / "gate")
    assert report["status"] == "INCONCLUSIVE"
    assert report["regression_gate"]["status"] == "BLOCKED"
    assert left not in path.read_text(encoding="utf-8") and right not in path.read_text(encoding="utf-8")
    monkeypatch.delenv("FIRST_API_KEY")
    monkeypatch.delenv("SECOND_API_KEY")
    second = tmp_path / "saved-again.json"; recorder.save(second)
    assert all(event["payload_redacted"] for event in read_json(second)["events"])
    assert check_recording(second, tmp_path / "gate-again")["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("field", ["adapter", "version", "request_id"])
def test_redaction_cannot_collapse_different_recording_identities(tmp_path, monkeypatch, field):
    secret = "SYNTHETIC_PRIVATE_IDENTITY"
    monkeypatch.setenv("IDENTITY_API_KEY", secret)
    recorder = BoundaryRecorder(secret if field == "adapter" else "safe-adapter", secret if field == "version" else "1.0")
    recorder.transform(user_trace(), deepcopy, request_id=secret if field == "request_id" else "safe-id")
    path = tmp_path / "private-identity.json"
    with pytest.raises(ValueError, match="redaction would change"):
        recorder.save(path)
    assert not path.exists()


def test_invalid_baseline_abstains_and_has_no_usable_gate(tmp_path):
    recorder = BoundaryRecorder("adapter", "1")
    orphan = [{"role": "tool", "tool_call_id": "orphan", "content": "x"}]
    recorder.transform(orphan, deepcopy)
    path = tmp_path / "orphan.json"; recorder.save(path)
    report = check_recording(path, tmp_path / "gate")
    assert report["status"] == "NEEDS_REVIEW"
    assert report["regression_gate"]["status"] == "BLOCKED"


def test_adapter_in_place_mutation_cannot_rewrite_its_own_baseline(tmp_path):
    recorder = BoundaryRecorder("adapter", "1")
    messages = user_trace()
    def mutation(value):
        value[1].pop("tool_calls")
        return value
    _, verdict = recorder.transform(messages, mutation)
    assert verdict["status"] == "FAIL"
    assert "tool_calls" in recorder.events[0]["payload"][1]


def test_future_gate_rejects_contract_checker_and_observed_fixture_drift(tmp_path):
    path, _ = capture(tmp_path, broken=False)
    for kind in ("contract", "runtime", "observed"):
        output = tmp_path / kind
        check_recording(path, output)
        assert run_gate(output).returncode == 0
        target = {"contract": output / "contract.json", "runtime": output / "_patchcourt_contract/semantic.py",
                  "observed": output / "observed-candidate.json"}[kind]
        target.write_bytes(target.read_bytes() + b"\n")
        failed = run_gate(output)
        assert failed.returncode == 1 and "changed" in failed.stderr.lower()


def test_preloaded_fake_comparator_cannot_bypass_the_verified_source(tmp_path):
    path, _ = capture(tmp_path)
    output = tmp_path / "gate"; check_recording(path, output)
    wrapper = '''import hashlib, pathlib, runpy, sys, types
folder=pathlib.Path(sys.argv[1])
namespace="_patchcourt_contract_"+hashlib.sha256((folder/"contract.json").read_bytes()).hexdigest()
fake=types.ModuleType(namespace+".semantic")
fake.compare_messages=lambda *args: {"status":"PASS","findings":[]}
sys.modules[namespace+".semantic"]=fake
sys.argv=[str(folder/"test_boundary_contract.py")]
runpy.run_path(sys.argv[0],run_name="__main__")
'''
    result = subprocess.run([sys.executable, "-I", "-c", wrapper, str(output)],
                            env={k: v for k, v in os.environ.items() if not k.startswith("PATCHCOURT_")},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1 and "SEMANTIC_CHANGE" in result.stderr


def test_timestamp_matching_fake_pyc_cannot_override_the_verified_source(tmp_path):
    path, _ = capture(tmp_path)
    output = tmp_path / "gate"; check_recording(path, output)
    source = output / "_patchcourt_contract/semantic.py"
    original, stat = source.read_bytes(), source.stat()
    forged = b'def compare_messages(*args):\n    return {"status":"PASS","findings":[]}\n'
    assert len(forged) < len(original)
    # Preserve both timestamp and byte size, which a normal timestamp pyc loader
    # would otherwise accept after the genuine .py source is restored.
    source.write_bytes(forged + b"#" * (len(original) - len(forged)))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    py_compile.compile(str(source), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    source.write_bytes(original)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    failed = run_gate(output)
    assert failed.returncode == 1 and "SEMANTIC_CHANGE" in failed.stderr


def test_unittest_discovery_cannot_preimport_an_unverified_snapshot_package(tmp_path):
    path, _ = capture(tmp_path, broken=False)
    output = tmp_path / "gate"; check_recording(path, output)
    runtime = output / "_patchcourt_contract"
    assert not (runtime / "__init__.py").exists()
    marker = tmp_path / "unverified-code-ran.txt"
    malicious_source = tmp_path / "fake_init.py"
    malicious_source.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n", encoding="utf-8")
    # A source-less legacy cache must not make discovery import this directory.
    py_compile.compile(str(malicious_source), cfile=str(runtime / "__init__.pyc"), doraise=True)
    (runtime / "version_snapshot.py").write_bytes(malicious_source.read_bytes())
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATCHCOURT_")}
    result = subprocess.run([sys.executable, "-I", "-S", "-m", "unittest", "discover", "-s", str(output),
                             "-p", "test_boundary_contract.py"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1 and "source changed" in result.stderr
    assert not marker.exists()


def test_prior_output_is_preserved_and_manual_old_capture_is_not_guessed(tmp_path):
    path, _ = capture(tmp_path)
    output = tmp_path / "gate"
    check_recording(path, output)
    before = (output / "report.json").read_bytes()
    with pytest.raises(ValueError, match="new output directory"): check_recording(path, output)
    assert (output / "report.json").read_bytes() == before
    legacy = {"adapter": "adapter", "version": "1", "events": []}
    path.write_text(json.dumps(legacy))
    with pytest.raises(ValueError, match="legacy captures"): read_recording(path)


def test_event_bounds_unknown_stage_and_invalid_request_selection_fail_closed(tmp_path):
    path, _ = capture(tmp_path)
    recording = read_json(path)
    with pytest.raises(ValueError, match="not captured"): select_recording(recording, "absent")
    recording["events"][0]["stage"] = "execute_shell"
    path.write_text(json.dumps(recording))
    with pytest.raises(ValueError, match="Unknown recording stage"): read_recording(path)


def test_recording_size_budgets_stop_before_output_or_unbounded_accumulation(tmp_path):
    recorder = BoundaryRecorder("bounded", "1")
    with pytest.raises(ValueError, match="1 MB"):
        recorder.record("framework_input", "x" * 1_000_001, "large")
    assert recorder.events == []
    for index in range(4):
        recorder.record("stream_event", "x" * 999_000, "stream-" + str(index))
    with pytest.raises(ValueError, match="aggregate payload"):
        recorder.record("stream_event", "x" * 999_000, "stream-5")
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * 8_000_001)
    with pytest.raises(ValueError, match="8 MB"): read_recording(path)


def test_python_only_payload_types_cannot_bypass_json_capture_or_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv("TUPLE_API_KEY", "synthetic-tuple-secret")
    recorder = BoundaryRecorder("adapter", "1")
    for payload in (("synthetic-tuple-secret",), {"nested": ("synthetic-tuple-secret",)}, {"items"}, object()):
        with pytest.raises(ValueError, match="JSON types only"):
            recorder.record("framework_input", payload, "x")
    assert recorder.events == []
    recorder.transform(user_trace(), deepcopy)
    recorder.events[0]["payload"] = ("synthetic-tuple-secret",)
    target = tmp_path / "unsupported.json"
    with pytest.raises(ValueError, match="JSON types only"): recorder.save(target)
    assert not target.exists()
