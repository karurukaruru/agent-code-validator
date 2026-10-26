"""Submission gates reject absent, substituted and integrity-broken evidence.

All records in these tests are synthetic fixtures; they are never release proof.
"""
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location("submission_check", Path(__file__).resolve().parents[1] / "scripts" / "submission_check.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def workflow(root, *, provider="nebius", model="nvidia/test-nemotron"):
    """Create a structural test fixture, not an authenticated cloud result."""
    from patchcourt.repair_plan import convert_trace, verify_plan
    from patchcourt.reproductions import nvidia_messages
    from patchcourt.semantic import compare_messages

    folder = root / "evidence" / "workflow"
    plan = {"source": "tool_calls", "id_field": "id", "name_field": "name", "arguments_field": "args",
            "arguments_encoding": "json", "preserve_legacy": True, "empty_content": "null"}
    mutant = dict(plan, id_field="name")
    trace = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "inventory-call", "type": "function", "function": {"name": "inventory", "arguments": '{"sku":"A"}'}},
        {"id": "price-call", "type": "function", "function": {"name": "price", "arguments": '{"sku":"A"}'}}]},
        {"role": "tool", "tool_call_id": "inventory-call", "content": json.dumps({"quantity": 3})},
        {"role": "tool", "tool_call_id": "price-call", "content": json.dumps({"price": 7})}]
    broken, repaired = nvidia_messages(trace), convert_trace(trace, plan)
    answer = {"sku": "A", "inventory_value": 21}
    task_start = [{"role": "system", "content": "Use the fixture tools before calculating."},
                  {"role": "user", "content": "Inventory value of A?"}]
    rows = []
    for name in ("repair-proposal-1", "task-turn-1", "task-turn-2"):
        message = trace[0] if name == "task-turn-1" else {"role": "assistant", "content": json.dumps(answer if name == "task-turn-2" else plan)}
        response = {"model": model, "choices": [{"message": message, "finish_reason": "tool_calls" if name == "task-turn-1" else "stop"}]}
        messages = ([{"role": "user", "content": "Propose the bounded mapping"}] if name.startswith("repair")
                    else task_start if name == "task-turn-1" else task_start + repaired)
        payload = {"model": model, "messages": messages}
        if name == "task-turn-1":
            payload["tools"] = [{"type": "function", "function": {"name": tool}} for tool in ("inventory", "price")]
        record = {"provider": provider, "endpoint": checker.OFFICIAL_API,
                  "status": "PASS", "http_status": 200, "provenance": "live HTTP attempt",
                  "timestamp": "2026-10-25T08:00:00+00:00", "parameters": payload,
                  "response": response, "raw_response": json.dumps(response)}
        write(folder / (name + ".json"), record)
        rows.append({"name": name, "status": "PASS", "evidence_file": name + ".json", "evidence_sha256": checker.digest(record)})
    report = {"run_id": "synthetic-test-run", "provider": provider, "model": model, "status": "PASS", "requests": rows,
              "plan": plan, "verification": verify_plan(plan),
              "mutation_check": {"status": "PASS", "mutant": mutant, "verification": verify_plan(mutant)},
              "task": {"status": "PASS", "answer": answer, "tools": [
                  {"tool": "inventory", "arguments": {"sku": "A"}, "result": {"quantity": 3}},
                  {"tool": "price", "arguments": {"sku": "A"}, "result": {"price": 7}}]},
              "live_boundaries": [{"input": trace, "broken": broken, "repaired": repaired,
                                   "before": compare_messages(trace, broken), "after": compare_messages(trace, repaired)}]}
    write(folder / "report.json", report)
    write(folder / "manifest.json", {"run_id": report["run_id"], "report_sha256": checker.digest(report)})
    return folder, report


def update_report(folder, report):
    write(folder / "report.json", report)
    write(folder / "manifest.json", {"run_id": report["run_id"], "report_sha256": checker.digest(report)})


def update_record(folder, report, **updates):
    path = folder / "task-turn-1.json"
    record = json.loads(path.read_text())
    record.update(updates)
    write(path, record)
    report["requests"][1]["evidence_sha256"] = checker.digest(record)
    update_report(folder, report)


def test_complete_structural_workflow(tmp_path):
    workflow(tmp_path)
    assert "3 hash-bound" in checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("provider,model", [("glm", "glm-5.3-flash"), ("deepseek", "deepseek-v4-flash"), ("nebius", "deepseek-ai/DeepSeek-V4-Flash")])
def test_development_provider_is_not_required_runtime(tmp_path, provider, model):
    workflow(tmp_path, provider=provider, model=model)
    with pytest.raises(ValueError, match="NVIDIA model through Nebius"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_report_change_is_detected(tmp_path):
    folder, report = workflow(tmp_path)
    report["task"]["answer"] = "unreviewed edit"
    write(folder / "report.json", report)
    with pytest.raises(ValueError, match="report hash"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_request_change_is_detected(tmp_path):
    folder, _ = workflow(tmp_path)
    path = folder / "task-turn-1.json"
    record = json.loads(path.read_text())
    record["usage"] = {"total_tokens": 1}
    write(path, record)
    with pytest.raises(ValueError, match="hash-bound"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_returned_model_substitution_is_rejected(tmp_path):
    folder, report = workflow(tmp_path)
    record = json.loads((folder / "task-turn-1.json").read_text())
    record["response"]["model"] = "a-different-model"
    update_record(folder, report, response=record["response"], raw_response=json.dumps(record["response"]))
    with pytest.raises(ValueError, match="Returned model identity"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("change", ["answer", "repaired", "checks", "corruption"])
def test_rehashed_pass_labels_do_not_replace_independent_execution(tmp_path, change):
    folder, report = workflow(tmp_path)
    if change == "answer":
        report["task"]["answer"]["inventory_value"] = 99
    elif change == "repaired":
        report["live_boundaries"][0]["repaired"][0]["tool_calls"][0]["id"] = "wrong-id"
    elif change == "checks":
        report["verification"]["checks"] = []
    else:
        report["mutation_check"]["verification"] = {"status": "REJECTED"}
    update_report(folder, report)
    with pytest.raises(ValueError):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("changes", [{"provenance": "mocked"}, {"mocked": True}, {"parameters": {}}, {"raw_response": "{}"}])
def test_inadequate_live_evidence_is_rejected_even_when_rehashed(tmp_path, changes):
    folder, report = workflow(tmp_path)
    update_record(folder, report, **changes)
    with pytest.raises(ValueError):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_discovery_is_not_inference(tmp_path):
    folder, report = workflow(tmp_path)
    for row in report["requests"]:
        record = json.loads((folder / (row["name"] + ".json")).read_text())
        record["endpoint"] = "https://api.tokenfactory.nebius.com/v1/models"
        write(folder / (row["name"] + ".json"), record)
        row["evidence_sha256"] = checker.digest(record)
    update_report(folder, report)
    with pytest.raises(ValueError, match="No successful Nebius NVIDIA task inference"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("field,value", [("verification", {"status": "REJECTED"}), ("mutation_check", {"status": "FAIL"}), ("task", {"status": "BLOCKED"}), ("live_boundaries", [])])
def test_product_success_cannot_be_inferred_from_http_alone(tmp_path, field, value):
    folder, report = workflow(tmp_path)
    report[field] = value
    update_report(folder, report)
    with pytest.raises(ValueError):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("url", ["http://127.0.0.1:8765", "https://localhost/demo", "https://example.com/project", "https://github.com/YOUR_NAME/repo", "https://user:password@host.com/video", "PENDING", "https://192.168.1.2/"])
def test_fake_and_private_urls_are_not_public_delivery(url):
    assert checker.public_url(url) is False


def test_youtube_homepage_is_not_a_video(tmp_path):
    with pytest.raises(ValueError, match="actual uploaded video"):
        checker.check_public(tmp_path, {"url": "https://www.youtube.com/", "verification": "proof.json"}, "youtube", None)


def test_missing_records_block_instead_of_passing(tmp_path):
    write(tmp_path / "submission-manifest.json", {"schema_version": 1})
    result = checker.check(tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["submission_complete"] is False
    assert all(row["status"] == "BLOCKED" for row in result["gates"])


def test_evidence_cannot_escape_project(tmp_path):
    with pytest.raises(ValueError, match="inside the project"):
        checker.local_file(tmp_path, "../outside.json")


@pytest.mark.parametrize("change", ["role", "refusal", "finish_reason", "tool_permission"])
def test_invalid_assistant_protocol_is_rejected_even_after_rehash(tmp_path, change):
    folder, report = workflow(tmp_path)
    record = checker.read_json(folder / "task-turn-1.json")
    choice = record["response"]["choices"][0]
    if change == "role":
        choice["message"]["role"] = "user"
    elif change == "refusal":
        choice["message"]["refusal"] = "Cannot comply"
    elif change == "finish_reason":
        choice["finish_reason"] = "stop"
    else:
        record["parameters"].pop("tools")
    update_record(folder, report, response=record["response"], raw_response=json.dumps(record["response"]), parameters=record["parameters"])
    with pytest.raises(ValueError):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_raw_duplicate_keys_are_not_collapsed_into_apparent_agreement(tmp_path):
    folder, report = workflow(tmp_path)
    record = checker.read_json(folder / "task-turn-1.json")
    raw = json.dumps(record["response"]).replace('"model":', '"model": "unapproved-model", "model":', 1)
    update_record(folder, report, raw_response=raw)
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_actual_followup_request_must_receive_the_recorded_repaired_tools(tmp_path):
    folder, report = workflow(tmp_path)
    path = folder / "task-turn-2.json"
    record = checker.read_json(path)
    record["parameters"]["messages"][-1]["content"] = '{"price":700}'
    write(path, record)
    report["requests"][2]["evidence_sha256"] = checker.digest(record)
    update_report(folder, report)
    with pytest.raises(ValueError, match="HTTP history"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_recorded_plan_must_be_the_actual_model_proposal(tmp_path):
    folder, report = workflow(tmp_path)
    path = folder / "repair-proposal-1.json"
    record = checker.read_json(path)
    record["response"]["choices"][0]["message"]["content"] = '{"unrelated":true}'
    record["raw_response"] = json.dumps(record["response"])
    write(path, record)
    report["requests"][0]["evidence_sha256"] = checker.digest(record)
    update_report(folder, report)
    with pytest.raises(ValueError, match="actual model proposal"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


@pytest.mark.parametrize("secret_field", ["authorization", "api_key", "refresh-token"])
def test_rehashed_secret_fields_are_rejected_without_printing_values(tmp_path, secret_field):
    folder, report = workflow(tmp_path)
    record = checker.read_json(folder / "task-turn-1.json")
    record[secret_field] = "synthetic-unredacted-credential"
    update_record(folder, report, **{secret_field: record[secret_field]})
    with pytest.raises(ValueError, match="sensitive field") as caught:
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")
    assert "synthetic-unredacted-credential" not in str(caught.value)


def test_request_filename_cannot_substitute_a_different_evidence_file(tmp_path):
    folder, report = workflow(tmp_path)
    report["requests"][0]["evidence_file"] = "../outside.json"
    update_report(folder, report)
    with pytest.raises(ValueError, match="filename"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")


def test_model_summary_cannot_disagree_with_the_actual_response(tmp_path):
    folder, report = workflow(tmp_path)
    report["requests"][1]["returned_model"] = "nvidia/a-different-nemotron"
    update_report(folder, report)
    with pytest.raises(ValueError, match="model summary"):
        checker.check_runtime(tmp_path, "evidence/workflow/report.json")
