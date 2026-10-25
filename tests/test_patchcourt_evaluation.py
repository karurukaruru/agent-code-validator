"""Protocol tests use synthetic replies; they do not claim live model quality."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import evaluation, providers
from patchcourt.counterexamples import cases
from patchcourt.evidence import digest, read_json


class EvaluationTests(unittest.TestCase):
    def predictions(self):
        return {"results": [{"id": f"case-{i:02}", "status": c["expected_status"], "reason": "synthetic response", "citations": []} for i, c in enumerate(cases())]}

    def test_rejects_missing_duplicate_and_fabricated_citation(self):
        good = self.predictions()
        ids = [x["id"] for x in good["results"]]
        for mutation in ("missing", "duplicate", "citation"):
            value = self.predictions()
            if mutation == "missing": value["results"].pop()
            if mutation == "duplicate": value["results"][-1]["id"] = ids[0]
            if mutation == "citation": value["results"][0]["citations"] = ["https://invented.invalid"]
            with self.assertRaises(ValueError): evaluation.validate_predictions(value, ids, [])

    def test_frozen_labels_hidden_and_reuse_revalidated(self):
        observed = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            def request(provider, payload):
                self.assertTrue((root / "plan.json").exists())
                self.assertEqual(provider, "glm")
                self.assertEqual(payload["model"], providers.GLM_MODEL)
                text = json.dumps(payload)
                self.assertNotIn("expected_status", text)
                self.assertNotIn("dropped-tool-calls", text)
                observed.append(payload)
                content = "[]" if len(observed) == 1 else json.dumps(self.predictions())
                return {"status": "PASS", "provenance": "synthetic", "usage": {"total_tokens": 12},
                        "response": {"model": providers.GLM_MODEL, "choices": [{"finish_reason": "stop", "message": {"content": content}}]}}
            with patch.object(providers, "request", side_effect=request), patch.object(providers, "search_docs", return_value={"status": "PASS", "documents": [{"url": "https://docs.langchain.com", "content": "Tool message documentation"}]}):
                report = evaluation.evaluate(root)
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(len(observed), 3)
            self.assertEqual(len(report["rows"]), 70)
            self.assertEqual(report["total_reported_tokens"], 36)
            reuse = [r for r in report["rows"] if r["arm"] == "E-scoped-reuse"]
            self.assertEqual(sum(r["details"]["knowledge_hit"] for r in reuse), 12)
            self.assertTrue(all(r["details"]["revalidated"] for r in reuse))
            self.assertEqual(digest(report), read_json(root / "manifest.json")["report_sha256"])
            with self.assertRaises(ValueError): evaluation.evaluate(root)

    def test_failed_requests_preserved_without_fabricated_results(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(providers, "request", return_value={"status": "FAIL", "reason": "HTTP error", "usage": None}), patch.object(providers, "search_docs", return_value={"status": "FAIL"}):
            report = evaluation.evaluate(Path(temp) / "run")
            self.assertEqual(report["status"], "PARTIAL")
            self.assertEqual(len(report["rows"]), 70)
            self.assertTrue(all(not r["executed"] for r in report["rows"] if r["arm"] in {"B-original-ACV-GLM", "C-GLM", "D-GLM-Tavily"}))
            self.assertTrue((Path(temp) / "run" / "C-GLM.json").exists())
            self.assertEqual(report["paired_retrieval"], [])

if __name__ == "__main__": unittest.main()
