import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from patchcourt.cli import main
from patchcourt.counterexamples import cases, minimize, tool_conversation, replay
from patchcourt.evidence import read_json
from patchcourt.recorder import BoundaryRecorder
from patchcourt.runner import demo, benchmark
from patchcourt.semantic import compare_messages, reconstruct_stream
from patchcourt.sentinel import inspect_repository

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_all_scheduled_mutations_and_controls(self):
        for case in cases():
            with self.subTest(case=case['id']):
                self.assertEqual(compare_messages(case['baseline'], case['candidate'])['status'], case['expected_status'])

    def test_empty_wrong_types_do_not_disappear(self):
        for field, invalid in [('tool_calls', {}), ('tool_calls', ''), ('additional_kwargs', []), ('additional_kwargs', None)]:
            with self.subTest(field=field, invalid=invalid):
                self.assertNotEqual(compare_messages([{'role':'assistant','content':''}], [{'role':'assistant','content':'',field:invalid}])['status'], 'PASS')

    def test_minimizer_preserves_failure(self):
        baseline=tool_conversation(); candidate=copy.deepcopy(baseline)
        candidate[0].pop('tool_calls')
        reduced=minimize(baseline,candidate)
        self.assertLessEqual(len(reduced['baseline']),len(baseline))
        self.assertEqual(compare_messages(reduced['baseline'],reduced['candidate'])['status'],'FAIL')

    def test_deterministic_task_replay(self):
        base=tool_conversation()
        self.assertEqual(replay(base)['inventory_value'],21)
        base[0].pop('tool_calls')
        self.assertEqual(replay(base)['status'],'FAIL')

    def test_recorder_snapshots_are_immutable(self):
        data=tool_conversation(); recorder=BoundaryRecorder('test','1')
        recorder.record('framework_input',data)
        data[0]['tool_calls'].clear()
        self.assertEqual(len(recorder.events[0]['payload'][0]['tool_calls']),2)
        with self.assertRaises(ValueError): recorder.record('shell',{})

    def test_stream_interleaving_and_completion(self):
        events=[{'choices':[{'index':0,'delta':{'tool_calls':[{'index':1,'id':'b','function':{'name':'second','arguments':'{}'}},{'index':0,'id':'a','function':{'name':'first','arguments':'{}'}}]},'finish_reason':None}]}, {'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}]}]
        self.assertEqual([c['id'] for c in reconstruct_stream(events)['tool_calls']],['a','b'])
        with self.assertRaises(ValueError): reconstruct_stream(events[:-1])

    def test_demo_knowledge_reuse_and_all_artifacts(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            first=demo(tmp); second=demo(tmp)
            self.assertFalse(first['knowledge']['prior_run_hit'])
            self.assertTrue(second['knowledge']['prior_run_hit'])
            self.assertFalse(second['knowledge']['verification_skipped'])
            for name in ['report.json','report.md','manifest.json','index.html','test_regression.py','ASM-ChatNVIDIA.md','minimal-counterexample.json','nvidia-repair.diff','crewai-repair.diff']:
                self.assertTrue((Path(tmp)/name).stat().st_size,name)
            self.assertEqual(read_json(Path(tmp)/'report.json')['mode'],'offline')

    def test_cli_exit_codes_for_ci(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base=Path(tmp)/'base.json'; candidate=Path(tmp)/'candidate.json'
            base.write_text(json.dumps(tool_conversation()),encoding='utf-8'); candidate.write_text(base.read_text(),encoding='utf-8')
            args=['check',str(base),str(candidate),'--output',str(Path(tmp)/'out')]
            self.assertEqual(main(args),0)
            data=tool_conversation(); data[0].pop('tool_calls'); candidate.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(main(args),1)
            candidate.write_text('invalid',encoding='utf-8')
            self.assertEqual(main(args),2)

    def test_repository_scan_never_claims_execution(self):
        result=inspect_repository(ROOT/'examples'/'demo_project','crewai','1','2')
        self.assertEqual(result['status'],'NEEDS_REVIEW')
        self.assertEqual(len(result['boundary_candidates']),4)

    def test_every_benchmark_arm_retained(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            report=benchmark(tmp)
            self.assertEqual(len(report['rows']),len(cases())*5)
            self.assertTrue(all(r['outcome']=='BLOCKED' for r in report['rows'] if r['arm'] in {'B-original-ACV','C-Nemotron','D-Nemotron-Tavily'}))


if __name__=='__main__': unittest.main()
