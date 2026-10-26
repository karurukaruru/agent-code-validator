"""Mocked model replies and real local execution; no network evidence."""
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from patchcourt.repair_plan import validate_plan, verify_plan
from patchcourt.live_workflow import run_live_workflow, project_glm_calls
from patchcourt.counterexamples import tool_conversation
from patchcourt import providers
from patchcourt.evidence import read_json, digest

PLAN={'source':'tool_calls','id_field':'id','name_field':'name','arguments_field':'args','arguments_encoding':'json','preserve_legacy':True,'empty_content':'null'}
def response(message):
    message={'role':'assistant',**message}
    return {'status':'PASS','http_status':200,'latency_ms':1,'usage':{'total_tokens':10},'provenance':'mocked transport','response':{'model':providers.GLM_MODEL,'choices':[{'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop','message':message}]}}
def replies():
    assistant=tool_conversation()[0]
    assistant['tool_calls'][0]['function']['arguments']='{"sku":"A"}'
    return [response({'content':json.dumps(PLAN)}),response(assistant),response({'content':'{"sku":"A","inventory_value":21}'})]

class LiveWorkflowTests(unittest.TestCase):
    def test_correct_mapping_passes_controls_and_mutation_fails(self):
        self.assertEqual(verify_plan(PLAN)['status'],'VERIFIED')
        for key,value in [('id_field','name'),('arguments_encoding','string'),('preserve_legacy',False)]:
            bad={**PLAN,key:value}
            self.assertEqual(verify_plan(bad)['status'],'REJECTED')

    def test_arbitrary_code_and_truthy_nonbool_rejected(self):
        for bad in [{**PLAN,'code':'__import__("os")'},{**PLAN,'source':'__class__'},{**PLAN,'preserve_legacy':'true'}]:
            with self.assertRaises(ValueError): validate_plan(bad)

    def run_case(self,values):
        with tempfile.TemporaryDirectory() as temp, patch.object(providers,'request',side_effect=values) as request:
            result=run_live_workflow(Path(temp)/'run')
            manifest=read_json(Path(temp)/'run/manifest.json')
            self.assertEqual(manifest['report_sha256'],digest(read_json(Path(temp)/'run/report.json')))
            self.assertTrue(all(call.args[0]=='glm' for call in request.call_args_list))
            return result

    def test_actual_local_pipeline_and_final_integrity(self):
        result=self.run_case(replies())
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['task']['answer']['inventory_value'],21)
        self.assertEqual(result['total_reported_tokens'],30)
        self.assertEqual(result['live_boundaries'][0]['before']['status'],'FAIL')
        self.assertEqual(result['live_boundaries'][0]['after']['status'],'PASS')

    def test_bad_plan_stops_before_task_and_preserves_failure(self):
        result=self.run_case([response({'content':json.dumps({**PLAN,'id_field':'name'})}) for _ in range(3)])
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['verification']['status'],'REJECTED')
        self.assertEqual(len(result['requests']),3)

    def test_rejected_candidate_preserved_before_successful_revision(self):
        result=self.run_case([response({'content':json.dumps({**PLAN,'source':'additional_kwargs'})})]+replies())
        self.assertEqual(result['status'],'PASS')
        self.assertEqual([r['verification']['status'] for r in result['repair_attempts']],['REJECTED','VERIFIED'])

    def test_wrong_actual_model_is_rejected(self):
        values=replies();values[0]['response']['model']='glm-5.3-flashx'
        self.assertEqual(self.run_case(values)['status'],'FAIL')

    def test_fabricated_answer_without_tools_is_rejected(self):
        values=replies();values.pop(1)
        self.assertEqual(self.run_case(values)['status'],'FAIL')

    def test_duplicate_tool_call_ids_rejected(self):
        values=replies();calls=values[1]['response']['choices'][0]['message']['tool_calls'];calls[1]['id']=calls[0]['id']
        self.assertEqual(self.run_case(values[:2])['status'],'FAIL')

    def test_wrong_final_numeric_answer_rejected(self):
        values=replies();values[-1]=response({'content':'{"sku":"A","inventory_value":22}'})
        self.assertEqual(self.run_case(values)['status'],'FAIL')

    def test_real_glm_ordinal_field_is_validated_before_projection(self):
        calls=tool_conversation()[0]['tool_calls']
        for i,c in enumerate(calls): c['index']=i
        result=project_glm_calls(calls)
        self.assertNotIn('index',result[0])
        self.assertIn('index',calls[0])
        calls[1]['index']=0
        with self.assertRaises(ValueError): project_glm_calls(calls)
        calls[1]['index']=True
        with self.assertRaises(ValueError): project_glm_calls(calls)

    def test_unrecognized_provider_fields_never_silently_disappear(self):
        calls=tool_conversation()[0]['tool_calls'];calls[0]['secret_semantics']='unknown'
        with self.assertRaises(ValueError): project_glm_calls(calls)

    def test_overwrite_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'prior').write_text('evidence')
            with self.assertRaises(ValueError): run_live_workflow(temp)

if __name__=='__main__': unittest.main()
