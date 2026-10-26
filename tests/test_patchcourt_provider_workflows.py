"""Synthetic responses exercise the actual bounded workflow; no live API calls."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.cli import main
from patchcourt.evidence import digest, read_json
from patchcourt.live_workflow import repair_identity, run_live_workflow
from patchcourt.reasoning import run_reasoning
from tests.test_patchcourt_live_workflow import replies


NEMOTRON = "nvidia/Nemotron-synthetic-test"
DOCUMENT = {"url": "https://docs.langchain.com/oss/python/langchain/messages",
            "title": "Messages", "content": "Normalized tool calls carry name, args and id."}


def model_replies(model):
    values = deepcopy(replies())
    for value in values:
        value["response"]["model"] = model
    return values


class ProviderIdentityTests(unittest.TestCase):
    def test_deepseek_uses_only_its_credential_and_fixed_origin(self):
        payload = providers.completion_payload("deepseek", [], json_object=True)
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-deepseek-key",
                                      "GLM_API_KEY": "synthetic-other-key"}, clear=True), patch.object(
                providers, "_transport", return_value=(200, {}, '{"choices":[]}')) as transport:
            record = providers.request("deepseek", payload)
        self.assertEqual(transport.call_args.args[:2],
                         ("https://api.deepseek.com/chat/completions", "synthetic-deepseek-key"))
        self.assertEqual(payload["model"], "deepseek-flash")
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", payload)
        self.assertEqual(record["provider"], "deepseek")

    def test_deepseek_never_falls_back_or_enables_thinking(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}, clear=True), patch.object(
                providers, "_transport") as transport:
            for override in ({"model": "deepseek-chat"}, {"thinking": {"type": "enabled"}},
                             {"reasoning_effort": "low"}):
                with self.subTest(override=override), self.assertRaises(ValueError):
                    providers.request("deepseek", {**providers.completion_payload("deepseek", []), **override})
            transport.assert_not_called()

    def test_deepseek_returned_alias_is_an_exact_allowlist(self):
        for returned in ("deepseek-flash", "DeepSeek-V4.1-Flash-1017"):
            result = providers.validate_response_model("deepseek", "deepseek-flash", returned)
            self.assertEqual(result["requested_model"], "deepseek-flash")
            self.assertEqual(result["returned_model"], returned)
        for returned in (None, "deepseek-chat", "DeepSeek-V4.1-Flash-1018", "deepseek-v4.1-flash-1017"):
            with self.subTest(returned=returned), self.assertRaises(ValueError):
                providers.validate_response_model("deepseek", "deepseek-flash", returned)

    def test_provider_output_limits_remain_bounded(self):
        self.assertEqual(providers.completion_payload("nebius", [], model=NEMOTRON)["max_tokens"], 2048)
        self.assertEqual(providers.completion_payload("deepseek", [])["max_tokens"], 4096)
        for provider, model, bad in (("nebius", NEMOTRON, 2049), ("deepseek", None, 8193),
                                     ("deepseek", None, True)):
            with self.subTest(provider=provider, bad=bad), self.assertRaises(ValueError):
                providers.completion_payload(provider, [], model=model, max_tokens=bad)

    def test_knowledge_identity_is_provider_and_model_specific(self):
        glm = repair_identity()
        deepseek = repair_identity("deepseek")
        nebius = repair_identity("nebius", NEMOTRON)
        self.assertEqual(glm["provider"], "glm")
        self.assertEqual(deepseek["model"], "deepseek-flash")
        self.assertEqual(len({digest(x) for x in (glm, deepseek, nebius)}), 3)

    def test_execution_identity_contains_public_source_and_reproducible_code_fingerprints(self):
        from patchcourt.live_workflow import VERIFICATION_FILES
        identity = repair_identity("deepseek")
        root = Path(providers.__file__).parent
        texts = {name: (root / name).read_text(encoding="utf-8").replace("\r\n", "\n") for name in VERIFICATION_FILES}
        self.assertEqual(identity["verification_sha256"], digest(texts))
        self.assertEqual(identity["verification_files_sha256"],
                         {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in texts.items()})
        self.assertEqual(len(identity["source_provenance"]["git_blob"]), 40)
        self.assertTrue(identity["source_provenance"]["reference_url"].startswith("https://github.com/"))
        self.assertIn("not a full installed SDK", identity["source_provenance"]["execution_kind"])
        self.assertNotIn(str(root), json.dumps(identity, allow_nan=False))


class ProviderWorkflowTests(unittest.TestCase):
    def test_deepseek_alias_workflow_executes_checks_mutation_and_real_local_tools(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
                providers, "request", side_effect=model_replies("DeepSeek-V4.1-Flash-1017")) as api:
            result = run_live_workflow(Path(temp) / "run", provider="deepseek")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["execution_identity"]["provider"], "deepseek")
            self.assertEqual(result["execution_identity"]["environment"], result["environment"])
            self.assertFalse(result["knowledge"]["enabled"])
            self.assertIsNone(result["knowledge"]["record_id"])
            self.assertEqual(len(result["verification"]["checks"]), 8)
            self.assertEqual(result["mutation_check"]["status"], "PASS")
            self.assertEqual(result["task"]["answer"]["inventory_value"], 21)
            self.assertIn("Does not establish", result["competition_eligibility"])
            for call, request in zip(api.call_args_list, result["requests"]):
                self.assertEqual(call.args[0], "deepseek")
                self.assertEqual(call.args[1]["thinking"], {"type": "disabled"})
                self.assertNotIn("reasoning_effort", call.args[1])
                self.assertEqual(request["returned_model"], "DeepSeek-V4.1-Flash-1017")
                self.assertEqual(request["evidence_sha256"], digest(read_json(Path(temp) / "run" / request["evidence_file"])))
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(["verify", str(Path(temp) / "run")]), 0)

    def test_nebius_requires_nvidia_nemotron_and_preserves_actual_model_identity(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
                providers, "request", side_effect=model_replies(NEMOTRON)) as api:
            result = run_live_workflow(Path(temp) / "run", provider="nebius", model=NEMOTRON)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model"], NEMOTRON)
        self.assertEqual(result["provider"], "nebius")
        self.assertTrue(all(c.args[0] == "nebius" and c.args[1]["max_tokens"] <= 2048 for c in api.call_args_list))
        with tempfile.TemporaryDirectory() as temp, patch.object(providers, "request") as api:
            for model in ("other/Nemotron", "nvidia/another-model"):
                with self.subTest(model=model), self.assertRaises(ValueError):
                    run_live_workflow(Path(temp) / model.replace("/", "-"), provider="nebius", model=model)
            api.assert_not_called()

    def test_nebius_discovery_selects_only_nvidia_nemotron(self):
        discovery = {"status": "PASS", "nemotron_models": ["other/Nemotron", NEMOTRON]}
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {}, clear=True), patch.object(
                providers, "discover_models", return_value=discovery) as discover, patch.object(
                providers, "request", side_effect=model_replies(NEMOTRON)):
            result = run_live_workflow(Path(temp) / "run", provider="nebius")
        discover.assert_called_once_with()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model"], NEMOTRON)

    def test_official_docs_enter_proposal_and_urls_are_reported(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(providers, "search_docs", return_value={
                "status": "PASS", "documents": [DOCUMENT]}) as search, patch.object(
                providers, "request", side_effect=model_replies("deepseek-flash")) as api:
            result = run_live_workflow(Path(temp) / "run", provider="deepseek", use_tavily=True)
        self.assertEqual(result["status"], "PASS")
        search.assert_called_once_with()
        proposal_input = json.loads(api.call_args_list[0].args[1]["messages"][1]["content"])
        self.assertEqual(proposal_input["official_documents"], [DOCUMENT])
        self.assertEqual(result["documentation_context"]["supplied_urls"], [DOCUMENT["url"]])

    def test_requested_retrieval_failure_stops_before_inference(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(providers, "search_docs", return_value={
                "status": "BLOCKED", "reason": "Missing TAVILY_API_KEY", "documents": []}), patch.object(
                providers, "request") as api:
            result = run_live_workflow(Path(temp) / "run", provider="deepseek", use_tavily=True)
        api.assert_not_called()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["retrieval"]["status"], "BLOCKED")

    def test_missing_returned_model_identity_is_not_a_successful_run(self):
        values = model_replies(NEMOTRON)
        values[0]["response"].pop("model")
        with tempfile.TemporaryDirectory() as temp, patch.object(providers, "request", side_effect=values[:1]):
            result = run_live_workflow(Path(temp) / "run", provider="nebius", model=NEMOTRON)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("model identity", result["reason"])
        self.assertNotIn("task", result)

    def test_deepseek_reasoning_uses_object_json_schema_prompt_and_checks_identity(self):
        proposal = {"hypothesis": "control", "test_cases": [], "repair_proposals": [], "citations": []}
        response = {"status": "PASS", "provenance": "synthetic", "response": {"model": "deepseek-flash", "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(proposal)}}]}}
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}, clear=True), patch.object(
                providers, "request", return_value=response) as api:
            result = run_reasoning("boundary source", {}, provider="deepseek")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["model_identity"]["returned_model"], "deepseek-flash")
        payload = api.call_args.args[1]
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertIn('"required"', payload["messages"][0]["content"])
        self.assertFalse(result["executed_repairs"])


if __name__ == "__main__":
    unittest.main()
