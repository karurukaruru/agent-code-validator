"""Synthetic transport tests for exact-model routing; no live calls."""
import json
import unittest
from unittest.mock import patch
from patchcourt import providers

class GLMRoutingTests(unittest.TestCase):
    def test_glm_key_only_goes_to_bigmodel(self):
        with patch.dict('os.environ',{'GLM_API_KEY':'synthetic-glm-secret','NEBIUS_API_KEY':'other-secret'},clear=True), patch.object(providers,'_transport',return_value=(200,{},'{"choices":[]}')) as transport:
            providers.request('glm',{'model':'glm-5.3-flash','max_tokens':1024})
            self.assertEqual(transport.call_args.args[:2],(providers.GLM_BASE+'/chat/completions','synthetic-glm-secret'))

    def test_no_flashx_or_other_model_fallback(self):
        with patch.dict('os.environ',{'GLM_API_KEY':'synthetic-glm-secret'},clear=True), patch.object(providers,'_transport') as transport:
            for model in ('glm-5.3-flashx','glm-5.3','nvidia/Nemotron'):
                with self.assertRaises(ValueError): providers.request('glm',{'model':model,'max_tokens':1024})
            transport.assert_not_called()

    def test_glm_errors_redact_configured_key(self):
        key='synthetic-glm-secret'
        with patch.dict('os.environ',{'GLM_API_KEY':key},clear=True), patch.object(providers,'_transport',return_value=(401,{},json.dumps({'error':key}))):
            record=providers.request('glm',{'model':providers.GLM_MODEL,'max_tokens':1024})
        self.assertEqual(record['status'],'FAIL')
        self.assertNotIn(key,json.dumps(record))

if __name__=='__main__': unittest.main()
