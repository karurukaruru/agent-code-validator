"""Synthetic transport tests validate the experiment, not model performance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers, release_evaluation as evaluation
from patchcourt.counterexamples import cases as historical_cases
from patchcourt.evidence import digest, read_json
from patchcourt.semantic import compare_messages


class OfficialDocumentationTests(unittest.TestCase):
    def test_specific_query_one_basic_credit_and_bounded_official_snippets(self):
        urls = ["https://api-docs.deepseek.com/guides/tool_calls", "https://docs.crewai.com/en/tools"]
        reply = {"status": "PASS", "response": {"results": [
            {"url": u, "title": "T" * 400, "content": "C" * 6000} for u in urls]}}
        with patch.object(providers, "request", return_value=reply) as request:
            result = providers.search_docs("DeepSeek tool reasoning_content history", ["api-docs.deepseek.com", "docs.crewai.com"], 2)
        payload = request.call_args.args[1]
        self.assertEqual(payload["query"], "DeepSeek tool reasoning_content history")
        self.assertEqual(payload["search_depth"], "basic")
        self.assertFalse(payload["include_answer"])
        self.assertFalse(payload["include_raw_content"])
        self.assertEqual(result["search_contract"]["search_credits_per_request"], 1)
        self.assertEqual([d["url"] for d in result["documents"]], urls)
        self.assertTrue(all(len(d["content"]) == 4000 and len(d["title"]) == 300 for d in result["documents"]))

    def test_url_origin_checks_include_empty_userinfo_and_nondefault_ports(self):
        rejected = ["https://@docs.nvidia.com/a", "https://:pw@docs.nvidia.com/a",
            "https://docs.nvidia.com:444/a", "https://docs.nvidia.com.evil.invalid/a",
            "https://evil-docs.nvidia.com/a", "http://docs.nvidia.com/a", "https://docs.nvidia.com/a\n",
            "https://.docs.nvidia.com/a", "https://x..docs.nvidia.com/a", "https://-x.docs.nvidia.com/a"]
        for url in rejected:
            with self.subTest(url=url), patch.object(providers, "request", return_value={"status": "PASS",
                "response": {"results": [{"url": url, "content": "bad"}]}}):
                record = providers.search_docs("NVIDIA message serializer", ["docs.nvidia.com"])
                self.assertEqual(record["status"], "INCONCLUSIVE")
                self.assertEqual(record["documents"], [])
        with patch.object(providers, "request", return_value={"status": "PASS", "response": {"results": [
                {"url": "https://child.docs.nvidia.com:443/a", "content": "official child host"}]}}):
            self.assertEqual(providers.search_docs("NVIDIA serializer", ["docs.nvidia.com"])["status"], "PASS")

    def test_invalid_options_do_not_make_a_request_and_empty_results_are_not_invented(self):
        with patch.object(providers, "request") as request:
            for kwargs in ({"query": " "}, {"query": "x" * 513}, {"max_results": True},
                           {"max_results": 4}, {"domains": "docs.python.org"},
                           {"domains": ["docs.python.org.evil.invalid"]}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    providers.search_docs(**kwargs)
            request.assert_not_called()
        with patch.object(providers, "request", return_value={"status": "PASS", "response": {"results": []}}):
            record = providers.search_docs()
        self.assertEqual(record["status"], "INCONCLUSIVE")
        self.assertEqual(record["documents"], [])


class RepeatedEvaluationTests(unittest.TestCase):
    def synthetic_request(self, root, observed, corrupt_first_c=False):
        def request(provider, payload):
            plan = read_json(root / "plan.json")
            self.assertEqual(provider, "deepseek")
            self.assertEqual(payload["model"], providers.DEEPSEEK_MODEL)
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(payload["max_tokens"], 2048)
            self.assertEqual(plan["limits"]["automatic_retries"], 0)
            text = json.dumps(payload)
            self.assertNotIn("expected_status", text)
            self.assertNotIn("developer-authored", text)
            for case in plan["corpus"]:
                self.assertNotIn(case["case"], text)
            index = len(observed)
            observed.append(payload)
            answers = {digest({"suite": "release-protocol-050-v1", "baseline": c["baseline"],
                "candidate": c["candidate"]})[:16]: c["expected_status"] for c in plan["corpus"]}
            content = "[]" if index % 3 == 0 else json.dumps({"results": [
                {"id": x["id"], "status": answers[x["id"][2:]], "reason": "synthetic", "citations": []}
                for x in plan["model_inputs"]]})
            return {"status": "PASS", "provenance": "synthetic fixture", "usage": {"total_tokens": 12},
                "latency_ms": 11, "response": {"model": providers.DEEPSEEK_MODEL, "choices": [
                    {"finish_reason": "length" if corrupt_first_c and index == 1 else "stop",
                     "message": {"role": "assistant", "content": content}}]}}
        return request

    def test_frozen_new_labels_hidden_repeated_arms_and_fresh_reuse(self):
        self.assertNotEqual(digest(evaluation.frozen_cases()), digest(historical_cases()))
        self.assertEqual(digest(evaluation.frozen_cases()), evaluation.FROZEN_CORPUS_SHA256)
        for case in evaluation.frozen_cases():
            self.assertEqual(compare_messages(case["baseline"], case["candidate"])["status"], case["expected_status"])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "run"
            observed = []
            with patch.object(providers, "request", side_effect=self.synthetic_request(root, observed)), patch.object(
                providers, "search_docs", return_value={"status": "PASS", "documents": [
                    {"url": "https://docs.nvidia.com/test", "content": "Synthetic official-document snippet"}]} ) as search, patch.object(
                    evaluation, "compare_messages", wraps=compare_messages) as compare:
                report = evaluation.run_evaluation(root)
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(len(observed), 6)
            self.assertEqual(len(report["rows"]), 120)
            self.assertEqual(len(report["paired_retrieval"]), 24)
            self.assertTrue(all(r["comparable"] and r["correctness_delta"] == 0 for r in report["paired_retrieval"]))
            self.assertEqual(report["total_reported_tokens"], 72)
            self.assertEqual(report["requests_missing_token_usage"], 0)
            self.assertEqual(report["total_reported_request_latency_ms"], 66)
            self.assertEqual(compare.call_count, 72)  # A once and E twice for every repeated example.
            self.assertEqual(search.call_count, 1)
            self.assertEqual(search.call_args.kwargs["query"], evaluation.QUERY)
            reuse = [r for r in report["rows"] if r["arm"] == "E-exact-reuse"]
            self.assertEqual(sum(r["details"]["knowledge_hit"] for r in reuse), 20)
            self.assertTrue(all(r["details"]["revalidated"] for r in reuse))
            self.assertEqual(digest(report), read_json(root / "manifest.json")["report_sha256"])
            self.assertIn("not an independent held-out set", read_json(root / "plan.json")["historical_corpus"])
            with self.assertRaises(ValueError):
                evaluation.run_evaluation(root)

    def test_all_failed_trials_and_unpaired_rows_remain_in_report(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(providers, "request", return_value={
            "status": "FAIL", "reason": "synthetic HTTP 429", "usage": None}), patch.object(providers, "search_docs",
                return_value={"status": "INCONCLUSIVE", "documents": [], "reason": "No official docs"}):
            root = Path(folder) / "run"
            report = evaluation.run_evaluation(root)
            self.assertEqual(report["status"], "PARTIAL")
            self.assertEqual(len(report["requests"]), 4)
            self.assertEqual(len(report["rows"]), 120)
            self.assertEqual(len(report["arm_errors"]), 6)
            self.assertEqual(len(report["paired_retrieval"]), 24)
            self.assertTrue(all(not r["comparable"] and r["correctness_delta"] is None for r in report["paired_retrieval"]))
            self.assertTrue((root / "trial-2-C-model.json").exists())
            self.assertEqual(report["metrics"]["C-model"]["unexecuted"], 24)
            self.assertEqual(report["requests_missing_token_usage"], 4)
            self.assertIsNone(report["total_reported_tokens"])

    def test_truncated_classification_does_not_get_retried_or_silently_discarded(self):
        with tempfile.TemporaryDirectory() as folder:
            root, observed = Path(folder) / "run", []
            with patch.object(providers, "request", side_effect=self.synthetic_request(root, observed, True)), patch.object(
                providers, "search_docs", return_value={"status": "PASS", "documents": [
                    {"url": "https://docs.nvidia.com/test", "content": "fixture"}]}):
                report = evaluation.run_evaluation(root)
            self.assertEqual(len(observed), 6)
            self.assertEqual(report["status"], "PARTIAL")
            self.assertEqual(len(report["arm_errors"]), 1)
            self.assertEqual(report["metrics"]["C-model"]["unexecuted"], 12)
            self.assertEqual(sum(r["comparable"] for r in report["paired_retrieval"]), 12)

    def test_budget_and_nemotron_identity_are_checked_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {}, clear=True), patch.object(providers, "request") as request:
            root = Path(folder) / "run"
            for kwargs in ({"trials": 1}, {"trials": True}, {"trials": 4}, {"provider": "glm"},
                           {"provider": "nebius"}, {"provider": "nebius", "model": "another/model"}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    evaluation.run_evaluation(root, **kwargs)
            self.assertFalse(root.exists())
            request.assert_not_called()

    def test_metrics_keep_false_positives_abstentions_and_failed_requests_distinct(self):
        rows = [{"executed": e, "expected": expected, "outcome": actual} for e, expected, actual in [
            (True, "FAIL", "FAIL"), (True, "PASS", "FAIL"), (True, "FAIL", "PASS"),
            (True, "FAIL", "INCONCLUSIVE"), (False, "FAIL", "ERROR")]]
        result = evaluation.score(rows)
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["false_negatives_including_abstentions"], 2)
        self.assertEqual(result["missed_positives_including_request_failures"], 3)


if __name__ == "__main__":
    unittest.main()
