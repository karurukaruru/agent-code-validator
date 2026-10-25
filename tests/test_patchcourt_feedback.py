"""Synthetic report tests only; these do not create platform findings."""
import copy
import tempfile
import unittest
from pathlib import Path
from patchcourt.feedback import summarize, render_feedback, wilson
from patchcourt.evidence import write_json
from patchcourt.providers import NEBIUS_BASE


def synthetic_report():
    return {"kind":"live provider reliability lab", "selected_model":"synthetic-test-model", "trials":[{"probe":"invalid_model_error","attempt":1,"status":"PASS","request":{"provider":"nebius","endpoint":NEBIUS_BASE+'/chat/completions',"provenance":"live HTTP attempt","http_status":404,"latency_ms":10,"timestamp":"synthetic test timestamp"}}]}


class FeedbackTests(unittest.TestCase):
    def test_expected_http_error_is_positive_contract_evidence(self):
        g=summarize(synthetic_report())['groups'][-1]
        self.assertEqual(g['classification'],'OBSERVED_SUCCESS')
        self.assertEqual((g['passed'],g['failed']),(1,0))

    def test_mocked_transport_never_becomes_platform_finding(self):
        r=synthetic_report(); r['trials'][0]['request']['provenance']='mocked transport'
        self.assertEqual(summarize(r)['status'],'BLOCKED')

    def test_timeout_without_http_is_not_platform_defect(self):
        r=synthetic_report(); r['trials'][0].update(status='FAIL'); r['trials'][0]['request']['http_status']=None
        self.assertEqual(summarize(r)['status'],'BLOCKED')

    def test_failure_is_observation_not_bug_claim(self):
        r=synthetic_report(); r['trials'][0].update(status='FAIL',probe='tool_call')
        g=summarize(r)['groups'][1]
        self.assertEqual(g['classification'],'OBSERVED_CONTRACT_FAILURE')
        self.assertEqual(g['failed'],1)

    def test_counts_keep_all_scheduled_blocked_trials(self):
        r=synthetic_report(); r['trials'] += [{'probe':'invalid_model_error','attempt':2,'status':'BLOCKED','request':{}}]
        g=summarize(r)['groups'][-1]
        self.assertEqual((g['planned'],g['observed_http_trials'],g['excluded_or_blocked']),(2,1,1))

    def test_small_samples_are_not_certainty(self):
        self.assertIsNone(wilson(0,0))
        self.assertLess(wilson(3,3)[0],0.5)
        self.assertGreater(wilson(0,3)[1],0.5)

    def test_blocked_draft_has_no_fabricated_strengths(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            r=synthetic_report(); r['trials']=[]
            write_json(Path(tmp)/'run'/'report.json',r)
            result=render_feedback(Path(tmp)/'run',Path(tmp)/'out')
            self.assertEqual(result['status'],'BLOCKED')
            self.assertIn('cannot yet claim',(Path(tmp)/'out'/'field-draft.txt').read_text())
            self.assertTrue((Path(tmp)/'out'/'feedback-summary.json').is_file())


if __name__=='__main__': unittest.main()
