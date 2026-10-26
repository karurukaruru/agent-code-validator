"""Validate recorded submission evidence without network calls or model requests.

Exit 0 means the recorded package is ready for the entrant's final review, not
that Devpost accepted it or that a judge can still reach a recorded URL. Exit 2
means a required gate is missing; exit 1 means supplied evidence is inconsistent.
Hashes detect changed local artifacts; they do not authenticate a provider.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from copy import deepcopy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DOCUMENTS = ("README.md", "LICENSE", "DEVPOST_SUBMISSION.md", "MOST_VALUABLE_FEEDBACK.md",
             "DEMO_SCRIPT.md", "JUDGE_TESTING.md", "SUBMISSION_CHECKLIST.md", "COMPETITION_CHANGELOG.md")
OFFICIAL_API = "https://api.tokenfactory.nebius.com/v1/chat/completions"
INFERENCE_APIS = {"nebius": OFFICIAL_API, "deepseek": "https://api.deepseek.com/chat/completions",
                  "glm": "https://open.bigmodel.cn/api/paas/v4/chat/completions"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def local_file(root, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("No local evidence file was supplied")
    root = Path(root).resolve()
    candidate = root / name
    if candidate.is_symlink():
        raise ValueError("Evidence must be a regular file, not a symbolic link")
    target = candidate.resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("Evidence must be an existing file inside the project")
    return target


def read_json(path):
    if path.stat().st_size > 8_000_000:
        raise ValueError("Evidence JSON exceeds 8 MB")
    return read_json_text(path.read_text(encoding="utf-8-sig"))


def public_evidence(value):
    """Reject recognizable unredacted credentials without loading credential files."""
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if re.search(r"\b(?:sk-|tvly-)[A-Za-z0-9_-]{8,}|(?i:bearer\s+(?!\[REDACTED\])[A-Za-z0-9._~+/-]{6,})|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", encoded):
        raise ValueError("Evidence contains credential-shaped content; value suppressed")
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = re.sub(r"[^a-z]", "", key.lower())
                if normalized in {"authorization", "apikey", "secret", "password", "accesstoken", "refreshtoken", "cookie", "setcookie"} and child not in (None, "", "[REDACTED]", "Bearer [REDACTED]"):
                    raise ValueError("Evidence contains an unredacted sensitive field; value suppressed")
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)


def public_url(value, hosts=None):
    if not isinstance(value, str) or re.search(r"(?i)placeholder|example\.|your[-_]|pending|TODO|[<>\s]", value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        return False
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".localhost")):
        return False
    try:
        if not ipaddress.ip_address(host).is_global:
            return False
    except ValueError:
        pass
    return hosts is None or host.lower() in hosts


def timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def check_runtime(root, name):
    report, records = verify_workflow(root, name, competition=True)
    actual = [record for _, record in records if record.get("status") == "PASS" and record.get("endpoint") == OFFICIAL_API]
    return "Verified workflow plus " + str(len(actual)) + " hash-bound NVIDIA/Nebius HTTP completions"


def verify_workflow(root, name, *, competition=False):
    """Bind a successful product workflow to its original HTTP history.

    Failed/blocked attempts remain in the returned record list and package. They
    never count as runtime success. This checks consistency, not authenticity.
    """
    from patchcourt.providers import is_nvidia_nemotron, validate_assistant_choice, validate_response_model
    root = Path(root).resolve()
    report_path = local_file(root, name)
    report = read_json(report_path)
    manifest = read_json(local_file(root, str(report_path.parent.relative_to(root) / "manifest.json")))
    if (not isinstance(report, dict) or not isinstance(manifest, dict) or not report.get("run_id")
            or manifest.get("run_id") != report["run_id"] or manifest.get("report_sha256") != digest(report)):
        raise ValueError("Runtime report hash does not match its manifest")
    public_evidence(report)
    public_evidence(manifest)
    provider = report.get("provider")
    model = report.get("model", "")
    if competition and (provider != "nebius" or not is_nvidia_nemotron(model)):
        raise ValueError("Runtime evidence must use an NVIDIA model through Nebius")
    if provider not in INFERENCE_APIS or not isinstance(model, str) or not model:
        raise ValueError("Unknown workflow provider or model")
    if provider == "nebius" and not is_nvidia_nemotron(model):
        raise ValueError("Nebius workflow must name the exact NVIDIA Nemotron model")
    if report.get("status") != "PASS" or report.get("verification", {}).get("status") != "VERIFIED":
        raise ValueError("Runtime workflow and independent repair verification must succeed")
    if report.get("mutation_check", {}).get("status") != "PASS" or report.get("task", {}).get("status") != "PASS":
        raise ValueError("Missing successful corruption control or real fixture-tool task")
    if not report.get("live_boundaries"):
        raise ValueError("Missing boundaries captured from the live tool conversation")
    requests = report.get("requests", [])
    if not isinstance(requests, list) or not 1 <= len(requests) <= 8:
        raise ValueError("Workflow requests must be a nonempty bounded list")
    actual, task_messages, task_records, records, names, proposals = [], [], [], [], set(), []
    for row in requests:
        if not isinstance(row, dict):
            raise ValueError("Malformed workflow request row")
        request_name = row.get("name", "")
        if not isinstance(request_name, str) or not re.fullmatch(r"(?:repair-proposal-[1-3]|task-turn-[1-4])", request_name) or request_name in names:
            raise ValueError("Unsafe or missing request evidence name")
        names.add(request_name)
        if row.get("evidence_file", request_name + ".json") != request_name + ".json":
            raise ValueError("Request evidence filename does not match its request name")
        record_path = local_file(root, str(report_path.parent.relative_to(root) / (request_name + ".json")))
        record = read_json(record_path)
        if row.get("evidence_sha256") != digest(record):
            raise ValueError("A request is not hash-bound to the workflow report")
        if not isinstance(record, dict):
            raise ValueError("Malformed provider request evidence")
        public_evidence(record)
        records.append((row, record))
        if record.get("provider") != provider:
            raise ValueError("Request provider differs from the workflow")
        if row.get("status", record.get("status")) != record.get("status"):
            raise ValueError("Request status differs from its hash-bound record")
        if any(key in row and row[key] != record.get(key) for key in ("http_status", "latency_ms", "usage")):
            raise ValueError("Request summary differs from its hash-bound HTTP metadata")
        if "requested_model" in row and row["requested_model"] != model:
            raise ValueError("Requested model summary differs from the workflow")
        if record.get("status") not in {"PASS", "FAIL", "BLOCKED"}:
            raise ValueError("Request evidence has an unfinished or unknown status")
        if any(record.get(key) is True for key in ("mocked", "synthetic", "fixture")):
            raise ValueError("A mocked or synthetic request cannot establish platform use")
        if record.get("status") != "PASS":
            if record.get("endpoint") not in (None, INFERENCE_APIS[provider]):
                raise ValueError("Failed completion record has an unexpected provider endpoint")
            continue  # Preserve failures without inventing a successful completion.
        if record.get("endpoint") != INFERENCE_APIS[provider]:
            raise ValueError("No successful Nebius NVIDIA task inference: a completion endpoint is required; discovery is insufficient")
        if type(record.get("http_status")) is not int or not 200 <= record["http_status"] < 300:
            raise ValueError("Successful completion has no successful HTTP status")
        if record.get("provenance") != "live HTTP attempt" or not timestamp(record.get("timestamp")):
            raise ValueError("Successful runtime request lacks live provenance or a timestamp")
        payload = record.get("parameters", {})
        if payload.get("model") != model or not payload.get("messages"):
            raise ValueError("Runtime request does not contain the claimed model and conversation")
        response = record.get("response", {})
        if not response.get("choices") or not isinstance(record.get("raw_response"), str):
            raise ValueError("Successful runtime request lacks an inspectable completion response")
        if read_json_text(record["raw_response"]) != response:
            raise ValueError("Parsed runtime response differs from the preserved HTTP response")
        if "returned_model" in row and row["returned_model"] != response.get("model"):
            raise ValueError("Returned model summary differs from the preserved response")
        if record.get("usage") != response.get("usage"):
            raise ValueError("Reported request usage differs from the preserved response")
        try:
            validate_response_model(provider, model, response.get("model"))
        except ValueError as exc:
            raise ValueError("Returned model identity does not match the requested NVIDIA model")
        message = validate_assistant_choice(response, allow_tools=bool(payload.get("tools")))
        if row.get("validation_status") == "FAIL":
            raise ValueError("A response rejected by the workflow cannot count as successful")
        if request_name.startswith("task-turn-"):
            task_messages.append(message)
            task_records.append(record)
        else:
            if task_records:
                raise ValueError("Repair proposals cannot follow task execution")
            proposals.append(message)
        actual.append(request_name)
    if not any(x.startswith("task-turn-") for x in actual):
        raise ValueError("No successful Nebius NVIDIA task inference; discovery is insufficient")
    if not any(x.startswith("repair-proposal-") for x in actual):
        raise ValueError("No successful Nebius NVIDIA repair proposal in this workflow")
    if read_json_text(proposals[-1].get("content", "")) != report.get("plan"):
        raise ValueError("Verified repair is not the last actual model proposal")
    verify_product_report(report, task_messages, task_records=task_records)
    return report, records


def verify_product_report(report, task_messages, *, task_records=None):
    """Rerun bounded local contracts instead of trusting recorded PASS strings."""
    from copy import deepcopy
    from patchcourt.repair_plan import convert_trace, verify_plan
    from patchcourt.semantic import compare_messages

    plan = report.get("plan")
    verified = verify_plan(plan)
    if verified != report.get("verification") or verified["status"] != "VERIFIED":
        raise ValueError("Fresh independent repair checks differ from the recorded verification")
    mutant = deepcopy(plan)
    mutant["id_field"] = "name"
    mutation = report["mutation_check"]
    if mutation.get("mutant") != mutant or verify_plan(mutant) != mutation.get("verification"):
        raise ValueError("Corruption control cannot be independently reproduced")
    if mutation["verification"].get("status") != "REJECTED":
        raise ValueError("The independent verifier did not reject the corrupted mapping")
    captured_calls = []
    for boundary in report["live_boundaries"]:
        baseline, broken, repaired = (boundary[key] for key in ("input", "broken", "repaired"))
        if compare_messages(baseline, broken)["status"] != "FAIL" or compare_messages(baseline, repaired)["status"] != "PASS":
            raise ValueError("Saved live boundary does not independently fail before and pass after repair")
        if convert_trace(baseline, plan) != repaired:
            raise ValueError("Saved repaired boundary differs from freshly executing the bounded mapping")
        captured_calls.extend(baseline[0].get("tool_calls", []))
    returned_calls = []
    for message in task_messages:
        for call in message.get("tool_calls", []):
            clean = deepcopy(call)
            clean.pop("index", None)
            returned_calls.append(clean)
    if captured_calls != returned_calls or not captured_calls:
        raise ValueError("Captured boundaries do not correspond to the preserved model tool calls")
    task = report["task"]
    answer = task.get("answer", {})
    if answer.get("sku") != "A" or type(answer.get("inventory_value")) not in (int, float) or answer["inventory_value"] != 21:
        raise ValueError("Fixture task did not independently recover inventory value 21")
    if not task_messages or read_json_text(task_messages[-1].get("content", "")) != answer:
        raise ValueError("Recorded task answer differs from the actual final model message")
    expected = {"inventory": {"quantity": 3}, "price": {"price": 7}}
    executed = task.get("tools", [])
    if {row.get("tool") for row in executed} != set(expected) or any(
        row.get("arguments") != {"sku": "A"} or row.get("result") != expected.get(row.get("tool")) for row in executed
    ):
        raise ValueError("Recorded fixture tool execution is incomplete or has inconsistent results")
    if task_records is not None:
        verify_task_history(report, task_records)


def verify_task_history(report, records):
    """Rebuild every task request from prior returned calls and fixture results."""
    from patchcourt.live_workflow import project_provider_calls
    expected_history, boundary_index, executed, ids = None, 0, [], set()
    boundaries = report["live_boundaries"]
    for index, record in enumerate(records):
        messages = record["parameters"]["messages"]
        if not isinstance(messages, list) or not messages:
            raise ValueError("Task HTTP history is missing")
        if expected_history is None:
            if any(m.get("role") in {"assistant", "tool"} for m in messages):
                raise ValueError("The first task request already contains unbound tool history")
            expected_history = deepcopy(messages)
        if messages != expected_history:
            raise ValueError("Task HTTP history differs from the preceding repaired boundary")
        assistant = record["response"]["choices"][0]["message"]
        calls = project_provider_calls(assistant.get("tool_calls", []))
        if not calls:
            if index != len(records) - 1 or boundary_index != len(boundaries):
                raise ValueError("Final model answer occurs before all saved tool boundaries")
            continue
        if boundary_index >= len(boundaries):
            raise ValueError("Actual model tool calls lack a corresponding boundary")
        boundary = boundaries[boundary_index]
        boundary_index += 1
        clean = {"role": "assistant", "content": assistant.get("content") or "", "tool_calls": calls}
        trace = [clean]
        for call in calls:
            if not isinstance(call.get("id"), str) or not call["id"] or call["id"] in ids:
                raise ValueError("Actual model calls have missing or repeated identities")
            ids.add(call["id"])
            function = call["function"]
            arguments = read_json_text(function["arguments"])
            tool = function["name"]
            if tool not in {"inventory", "price"} or arguments != {"sku": "A"}:
                raise ValueError("Actual model call exceeds the fixture tool capability")
            result = {"quantity": 3} if tool == "inventory" else {"price": 7}
            executed.append({"tool": tool, "arguments": arguments, "result": result})
            trace.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
        if boundary["input"] != trace:
            raise ValueError("Boundary tool results differ from the actual fixture calls")
        repaired = deepcopy(boundary["repaired"])
        if assistant.get("reasoning_content") is not None:
            repaired[0]["reasoning_content"] = assistant["reasoning_content"]
        expected_history.extend(repaired)
    if executed != report["task"]["tools"] or not records or records[-1]["response"]["choices"][0]["message"].get("tool_calls"):
        raise ValueError("Actual HTTP conversation does not match the recorded executed tools and final answer")


def read_json_text(value):
    from patchcourt.evidence import strict_json
    return strict_json(value)


def check_public(root, item, category, source_commit):
    hosts = {"github.com", "gitlab.com", "bitbucket.org"} if category == "source" else None
    if category == "youtube":
        hosts = {"www.youtube.com", "youtube.com", "youtu.be"}
    if not isinstance(item, dict) or not public_url(item.get("url"), hosts):
        raise ValueError("A concrete public HTTPS URL is required")
    parsed = urlsplit(item["url"])
    if category == "source" and len([part for part in parsed.path.split("/") if part]) < 2:
        raise ValueError("Source URL must identify a repository")
    if category == "youtube":
        video_id = parsed.path.strip("/") if parsed.hostname == "youtu.be" else parse_qs(parsed.query).get("v", [""])[0]
        if parsed.hostname != "youtu.be" and parsed.path != "/watch":
            video_id = ""
        if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id):
            raise ValueError("YouTube URL must identify the actual uploaded video")
    proof = read_json(local_file(root, item.get("verification")))
    if proof.get("url") != item["url"] or proof.get("http_status") != 200:
        raise ValueError("Anonymous public-access record must match this exact URL and HTTP 200")
    if proof.get("access") != "anonymous" or not timestamp(proof.get("checked_at")):
        raise ValueError("Missing dated anonymous-access verification")
    snapshot = local_file(root, proof.get("evidence_file"))
    if proof.get("evidence_sha256") != sha256(snapshot) or proof.get("content_verified") is not True:
        raise ValueError("Public access record must bind inspected content, not just an HTTP success code")
    if category == "source" and (not re.fullmatch(r"[a-f0-9]{40}", source_commit or "") or proof.get("commit") != source_commit):
        raise ValueError("Public source verification must identify the final 40-character commit")
    if category == "demo" and (proof.get("functional_smoke_test") != "PASS" or proof.get("free_judge_access") is not True):
        raise ValueError("The demo/test-build requires a recorded functional check and free judge access")
    if category == "youtube" and proof.get("visibility") != "public":
        raise ValueError("The recorded YouTube visibility must be public")
    return "Dated anonymous access recorded; availability must be rechecked before submission"


def check_video(root, item):
    video = local_file(root, item.get("file"))
    manifest = read_json(local_file(root, item.get("manifest")))
    if manifest.get("sha256") != sha256(video):
        raise ValueError("Video bytes do not match the reviewed video manifest")
    duration = manifest.get("duration_seconds")
    if type(duration) not in (int, float) or not 0 < duration < 180:
        raise ValueError("The actual local video must be shorter than 180 seconds")
    if manifest.get("visual_review") != "PASS" or item.get("english_reviewed") is not True:
        raise ValueError("Missing video visual/English review")
    if item.get("competition_runtime_shown") is not True or item.get("spoken_platform_attribution") is not True:
        raise ValueError("Video has not been reviewed for actual Nebius/NVIDIA runtime and spoken attribution")
    return "Hash-checked reviewed English video, shorter than three minutes"


def check_form(root, name):
    record = read_json(local_file(root, name))
    fields = ("required_fields_reviewed", "feedback_entered", "entrant_eligibility_confirmed",
              "ownership_and_licenses_confirmed", "english_materials_reviewed", "free_judge_access_through_judging_confirmed")
    if record.get("kind") != "authenticated Devpost form review" or not timestamp(record.get("reviewed_at")):
        raise ValueError("Authenticated form review has not been recorded")
    if any(record.get(field) is not True for field in fields):
        raise ValueError("Entrant/form review has unresolved required checks")
    return "Entrant review recorded; legal/account declarations are not independently verified"


def check(root, manifest_name="submission-manifest.json"):
    root = Path(root).resolve()
    config = read_json(local_file(root, manifest_name))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported submission manifest version")
    gates = []
    def gate(name, supplied, fn):
        if not supplied:
            gates.append({"gate": name, "status": "BLOCKED", "detail": "Required evidence is not yet supplied"})
            return
        try:
            detail = fn()
            gates.append({"gate": name, "status": "PASS", "detail": detail})
        except (ValueError, TypeError, KeyError, OSError, AttributeError) as exc:
            # Print validation explanations only; never dump evidence or credentials.
            gates.append({"gate": name, "status": "FAIL", "detail": str(exc) if isinstance(exc, ValueError) else "Evidence is malformed or unreadable"})
    for name in DOCUMENTS:
        gate("document:" + name, (root / name).is_file(), lambda name=name: (
            "Present and nonempty" if local_file(root, name).stat().st_size > 100 else (_ for _ in ()).throw(ValueError("Document is too short"))))
    runtime = config.get("runtime_workflow")
    gate("nvidia_nebius_runtime", runtime, lambda: check_runtime(root, runtime))
    for category in ("source", "demo", "youtube"):
        item = config.get("public_links", {}).get(category)
        gate("public:" + category, item and item.get("url") and item.get("verification"),
             lambda item=item, category=category: check_public(root, item, category, config.get("source_commit")))
    video = config.get("video", {})
    gate("video", video, lambda: check_video(root, video))
    feedback = config.get("feedback_review")
    def feedback_check():
        record = read_json(local_file(root, feedback))
        if record.get("document_sha256") != sha256(root / "MOST_VALUABLE_FEEDBACK.md") or record.get("observations_backed_by_records") is not True:
            raise ValueError("Feedback review must bind the current document and confirm evidence-backed observations")
        if not runtime or record.get("runtime_report_sha256") != sha256(local_file(root, runtime)):
            raise ValueError("Feedback review must bind the actual required-platform workflow")
        if not timestamp(record.get("reviewed_at")):
            raise ValueError("Feedback review is undated")
        return "Current feedback and required-platform evidence are bound to a dated technical review"
    gate("feedback", feedback, feedback_check)
    gate("entrant_and_form_review", config.get("form_review"), lambda: check_form(root, config["form_review"]))
    states = {row["status"] for row in gates}
    status = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "READY_FOR_ENTRANT_REVIEW"
    return {"schema_version": 1, "status": status, "submission_complete": False,
            "scope": "Deterministic validation of local records; no live access, eligibility determination, platform authentication or Devpost submission",
            "gates": gates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="submission-manifest.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.root, args.manifest)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        result = {"status": "FAIL", "submission_complete": False, "error": str(exc) if isinstance(exc, ValueError) else "Submission manifest is missing, malformed or unreadable"}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "READY_FOR_ENTRANT_REVIEW" else 2 if result["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
