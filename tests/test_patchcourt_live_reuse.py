"""Synthetic provider replies; real plan checks and scoped persistence execute."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from patchcourt import providers
from patchcourt.evidence import digest, read_json, write_json
from patchcourt.live_workflow import run_live_workflow, repair_identity
from patchcourt.knowledge import KnowledgeStore
from tests.test_patchcourt_live_workflow import PLAN, replies


class LiveReuseTests(unittest.TestCase):
    def test_repeat_skips_proposal_but_reruns_verification_and_task(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'knowledge'
            with patch.object(providers,'request',side_effect=replies()) as first:
                a=run_live_workflow(root/'first',knowledge_dir=cache)
            self.assertEqual(a['status'],'PASS');self.assertEqual(first.call_count,3)
            self.assertTrue(a['knowledge']['saved'])
            with patch.object(providers,'request',side_effect=replies()[1:]) as second:
                b=run_live_workflow(root/'second',knowledge_dir=cache)
            self.assertEqual(b['status'],'PASS');self.assertEqual(second.call_count,2)
            self.assertTrue(b['knowledge']['hit']);self.assertTrue(b['knowledge']['revalidated'])
            self.assertEqual(b['repair_source'],'cached_verified_plan')
            self.assertEqual(b['repair_attempts'],[])
            self.assertEqual(len(b['verification']['checks']),8)
            self.assertEqual(b['mutation_check']['status'],'PASS')
            self.assertEqual(b['task']['answer']['inventory_value'],21)
            self.assertEqual(digest(b),read_json(root/'second/manifest.json')['report_sha256'])

    def test_tampered_cache_fails_without_spending_or_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'knowledge'
            with patch.object(providers,'request',side_effect=replies()):
                run_live_workflow(root/'first',knowledge_dir=cache)
            path=next(cache.glob('*.json'));record=read_json(path)
            record['evidence']['plan']['id_field']='name';write_json(path,record)
            before=path.read_bytes()
            with patch.object(providers,'request') as api:
                result=run_live_workflow(root/'second',knowledge_dir=cache)
            api.assert_not_called();self.assertEqual(result['status'],'FAIL')
            self.assertEqual(path.read_bytes(),before)

    def test_valid_checksum_cannot_make_invalid_plan_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'knowledge'
            KnowledgeStore(cache).save(repair_identity(),{'status':'PASS','execution':True,'plan':{**PLAN,'id_field':'name'}})
            with patch.object(providers,'request') as api:
                result=run_live_workflow(root/'run',knowledge_dir=cache)
            api.assert_not_called();self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['verification']['status'],'REJECTED')

    def test_changed_verifier_scope_requires_new_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'knowledge';identity=repair_identity()
            KnowledgeStore(cache).save(identity,{'status':'PASS','execution':True,'plan':PLAN})
            with patch('patchcourt.live_workflow.repair_identity',return_value={**identity,'verification_sha256':'changed'}), patch.object(providers,'request',side_effect=replies()) as api:
                result=run_live_workflow(root/'run',knowledge_dir=cache)
            self.assertEqual(result['status'],'PASS');self.assertEqual(api.call_count,3)
            self.assertFalse(result['knowledge']['hit'])
            self.assertEqual(len(list(cache.glob('*.json'))),2)

    def test_failed_task_never_saves_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'knowledge';values=replies()
            values[-1]['response']['choices'][0]['message']['content']='{"sku":"A","inventory_value":22}'
            with patch.object(providers,'request',side_effect=values):
                result=run_live_workflow(root/'run',knowledge_dir=cache)
            self.assertEqual(result['status'],'FAIL')
            self.assertFalse(result['knowledge']['saved'])
            self.assertEqual(list(cache.glob('*.json')),[])

if __name__=='__main__': unittest.main()
