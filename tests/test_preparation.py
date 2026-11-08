import json
import os
import sys
from pathlib import Path
import threading
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from sheetkeeper.contracts import inspect_csv, validate_plan, validate_result
from sheetkeeper.planner import make_plan, SAMPLE_QUESTION, infer
from sheetkeeper.sandbox import DockerSandbox, bounded_capture
from sheetkeeper.jobs import Jobs
from sheetkeeper import server
from sheetkeeper.localization import CATALOG, language

CSV = (Path(__file__).parents[1] / "fixtures/sales.csv").read_text()
RESULT = {"rows": 6, "groups": [{"label": "Busca", "value": 2000}, {"label": "Social", "value": 1500},
                              {"label": "Indicacao", "value": 2500}], "total": 6000}


class FakeSandbox:
    def __init__(self, destroyed=True, timed_out=False):
        self.destroyed, self.timed_out = destroyed, timed_out
    def preflight(self):
        return {"ready": True}
    def execute(self, code, csv_text, timeout):
        return {"result": None if self.timed_out else RESULT, "exit_code": -9 if self.timed_out else 0,
                "timed_out": self.timed_out, "destroyed": self.destroyed, "image_id": "fake-test-image",
                "container": "fake-test-container", "elapsed_ms": 3}


class ContractsTests(unittest.TestCase):
    def test_valid_csv_and_quoted_cells(self):
        self.assertEqual(inspect_csv(CSV)["rows"], 6)
        self.assertEqual(inspect_csv('name,value\n"a,b",4\n')["rows"], 1)
    def test_rejects_empty_duplicate_ragged_and_oversized(self):
        for csv in ('', 'a,a\n1,2', 'a,b\n1', 'a\n'+('x'*4001), 'a\n'+'1\n'*2001, 'a\n\x00'):
            with self.subTest(csv=csv[:30]), self.assertRaises(ValueError): inspect_csv(csv)
    def test_result_rejects_forged_total_nonfinite_and_extra_artifacts(self):
        self.assertEqual(validate_result(RESULT)["total"], 6000)
        for value in ({**RESULT, "total": 9}, {**RESULT, "total": float('nan')},
                      {**RESULT, "groups": [{"label": "a", "value": True}]},
                      {**RESULT, "artifact": "../../secret"}, {**RESULT, "rows": True}):
            with self.assertRaises(ValueError): validate_result(value)
    def test_plan_only_accepts_exact_contract_and_valid_syntax(self):
        for plan in ({"summary": "hi", "code": "x=", "extra": 2}, {"summary": "hi", "code": "x="},
                     {"summary": "hi", "code": "x"*25000}):
            with self.assertRaises(ValueError): validate_plan(plan)
    def test_sample_never_uses_inference_and_rejects_other_questions(self):
        with patch('sheetkeeper.planner.infer', side_effect=AssertionError('must not call')):
            _, provider = make_plan(inspect_csv(CSV), SAMPLE_QUESTION, 'sample')
            self.assertFalse(provider['model_called'])
            with self.assertRaises(ValueError): make_plan(inspect_csv(CSV), 'Delete everything', 'sample')
    def test_inference_disabled_before_any_network_call(self):
        with patch.dict(os.environ, {'SHEETKEEPER_ENABLE_INFERENCE': '0'}), patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError): infer([])
            call.assert_not_called()
    def test_vultr_request_uses_only_metadata_and_caps_completion(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps({'model':'test-model','choices':[{'finish_reason':'stop',
                'message':{'content':json.dumps({'summary':'Summary','code':'pass'})}}],'usage':{}}).encode()
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'SHEETKEEPER_ENABLE_INFERENCE':'1','VULTR_INFERENCE_API_KEY':'fake-test-key',
                                     'VULTR_INFERENCE_MODEL':'test-model',
                                     'SHEETKEEPER_INFERENCE_BUDGET_FILE':str(Path(temp)/'budget.json')}), patch('urllib.request.urlopen', return_value=Response()) as call:
            make_plan(inspect_csv(CSV), 'Sum revenue', 'vultr')
            request = call.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(request.full_url, 'https://api.vultrinference.com/v1/chat/completions')
            self.assertEqual(payload['max_completion_tokens'], 2500)
            self.assertEqual(payload['response_format'], {'type': 'json_object'})
            self.assertEqual(payload['reasoning'], {'enabled': False})
            self.assertNotIn('1200', request.data.decode())
            self.assertNotIn('fake-test-key', request.data.decode())


    def test_languages_preserve_data_and_never_call_model_for_sample(self):
        with patch('sheetkeeper.planner.infer', side_effect=AssertionError('must not call')):
            for locale in ('pt-BR', 'pt-PT', 'en-US', 'en-GB', 'es-ES', 'es-MX'):
                entry=CATALOG[language(locale)]
                plan,provider=make_plan(inspect_csv(CSV),entry['sampleQuestion'],'sample',locale)
                self.assertEqual(plan['summary'],entry['sampleSummary'])
                self.assertIn("row['revenue']",plan['code'])
                self.assertFalse(provider['model_called'])
    def test_model_language_instruction_is_bounded_and_keeps_columns(self):
        with patch('sheetkeeper.planner.infer', return_value=({},{})) as call:
            make_plan(inspect_csv(CSV),'Agrupa por canal','vultr','es-MX')
            messages=call.call_args.args[0]
            self.assertIn('Write the summary in Spanish.',messages[0]['content'])
            self.assertEqual(json.loads(messages[1]['content'])['columns'],['channel','revenue'])
            make_plan(inspect_csv(CSV),'test','vultr','es; leak secrets')
            self.assertIn('Write the summary in English.',call.call_args.args[0][0]['content'])
    def test_catalogs_cover_interface_and_controller_messages(self):
        import ast,re
        root=Path(__file__).parents[1]
        for entry in CATALOG.values():
            self.assertEqual(set(entry),set(CATALOG['pt']))
            self.assertEqual(set(entry['messages']),set(CATALOG['pt']['messages']))
            self.assertTrue(all(entry[k] for k in entry if k!='messages'))
        html=(root/'web/index.html').read_text()
        for key in re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"',html):
            self.assertIn(key,CATALOG['en'])
        for path in (root/'src/sheetkeeper').glob('*.py'):
            if path.name.startswith('._'):continue
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='ValueError' and node.args and isinstance(node.args[0],ast.Constant):
                    text=node.args[0].value
                    if isinstance(text,str):self.assertIn(text,CATALOG['en']['messages'])


class IsolationPreparationTests(unittest.TestCase):
    def test_attachment_output_and_time_are_bounded(self):
        # Trusted test helpers only. This does not execute model-generated code on the host.
        output, _, timeout, limited = bounded_capture([sys.executable, '-c', 'print("x"*220000)'], b'', 2)
        self.assertTrue(limited); self.assertLessEqual(len(output),200000)
        _, _, timeout, _ = bounded_capture([sys.executable, '-c', 'import time;time.sleep(5)'], b'', .1)
        self.assertTrue(timeout)
    def test_unavailable_daemon_does_not_fall_back_to_host(self):
        sandbox = DockerSandbox(binary='/fake/docker')
        with patch('subprocess.run', side_effect=OSError):
            self.assertFalse(sandbox.preflight()['ready'])
        with self.assertRaises(RuntimeError): sandbox.command('test')
    def test_sandbox_command_has_limits_no_secret_mounts_or_network(self):
        sandbox= DockerSandbox(binary='docker'); sandbox.image_id='sha256:test'
        args=sandbox.command('sheetkeeper-test')
        for flag in ('--network=none','--read-only','--user=10001:10001','--cap-drop=ALL','--memory=256m',
                     '--pids-limit=64','--security-opt=no-new-privileges=true','--pull=never'):
            self.assertIn(flag,args)
        self.assertFalse(any(a in ('-v','--mount','--privileged','--env-file','--env') for a in args))
    def wait(self,jobs,job_id):
        for _ in range(100):
            status=jobs.get(job_id)['status']
            if status != 'running': return status
            time.sleep(.01)
        self.fail('job did not terminate')
    def test_validated_job_exports_receipt_without_raw_input(self):
        jobs=Jobs(FakeSandbox()); planned=jobs.plan(CSV,SAMPLE_QUESTION,'sample')
        jobs.run(planned['id']); self.assertEqual(self.wait(jobs,planned['id']),'completed')
        result=jobs.get(planned['id'])
        self.assertNotIn('csv',result); self.assertTrue(result['receipt']['destroyed'])
        self.assertEqual(len(result['receipt']['input_sha256']),64)
        with self.assertRaises(ValueError): jobs.run(planned['id'])
    def test_cleanup_failure_blocks_next_task(self):
        jobs=Jobs(FakeSandbox(destroyed=False)); planned=jobs.plan(CSV,SAMPLE_QUESTION,'sample')
        jobs.run(planned['id']); self.assertEqual(self.wait(jobs,planned['id']),'failed')
        with self.assertRaises(ValueError): jobs.plan(CSV,SAMPLE_QUESTION,'sample')
    def test_containment_report_requires_timeout_and_destruction(self):
        jobs=Jobs(FakeSandbox(timed_out=True)); planned=jobs.plan(CSV,SAMPLE_QUESTION,'sample')
        jobs.run(planned['id'],True); self.assertEqual(self.wait(jobs,planned['id']),'contained')
        self.assertIsNone(jobs.get(planned['id'])['result'])
    def test_expired_capability_cannot_read_result(self):
        jobs=Jobs(FakeSandbox()); planned=jobs.plan(CSV,SAMPLE_QUESTION,'sample')
        jobs.jobs[planned['id']]['created'] -= 3601
        with self.assertRaises(KeyError): jobs.get(planned['id'])
        with self.assertRaises(KeyError): jobs.run(planned['id'])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SHEETKEEPER_ACCESS_CODE':'','SHEETKEEPER_ALLOWED_HOST':''})
        self.env.start()
        self.srv=server.create_server(port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base=f'http://127.0.0.1:{self.srv.server_port}'
    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.env.stop()
    def request(self,path,body=None,headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.base+path,
            data=json.dumps(body).encode() if body else None,
            headers=headers or {'Content-Type':'application/json'}))
    def test_http_plan_ready_is_not_execution_and_receipt_unavailable(self):
        with self.request('/api/plan',{'csv':CSV,'question':SAMPLE_QUESTION,'mode':'sample'}) as response:
            job=json.load(response)
        self.assertEqual(job['status'],'ready'); self.assertIsNone(job['receipt'])
        with self.assertRaises(urllib.error.HTTPError) as ctx: self.request('/api/jobs/'+job['id']+'/evidence')
        self.assertEqual(ctx.exception.code,409)
    def test_rejects_foreign_origin_and_dns_rebinding_host(self):
        for headers in ({'Origin':'https://evil.example'}, {'Host':'evil.example'}):
            with self.assertRaises(urllib.error.HTTPError) as ctx: self.request('/api/sample',headers=headers)
            self.assertEqual(ctx.exception.code,403)
    def test_auth_is_enforced_at_api_not_only_ui(self):
        self.srv.access_code='synthetic-test-code'
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/sample')
        self.assertEqual(ctx.exception.code,401)
        with self.request('/api/sample',headers={'Authorization':'Bearer synthetic-test-code'}) as response:
            self.assertIn('csv',json.load(response))
    def test_generated_paths_are_not_served_and_public_bind_is_gated(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/../../.env')
        self.assertEqual(ctx.exception.code,404)
        with self.assertRaises(ValueError):server.create_server('0.0.0.0',0)
    def test_api_localization_and_catalog_asset(self):
        for locale in ('pt-BR','en-US','es-MX'):
            headers={'Content-Type':'application/json','X-SheetKeeper-Locale':locale}
            entry=CATALOG[language(locale)]
            with self.request('/api/plan',{'csv':CSV,'question':entry['sampleQuestion'],'mode':'sample'},headers) as response:
                job=json.load(response)
            self.assertEqual(job['summary'],entry['sampleSummary'])
            self.assertIsNone(job['receipt'])
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/plan',{'csv':'','question':'test','mode':'sample'},headers)
            data=json.load(ctx.exception)
            self.assertEqual(data['error'],entry['messages'][data['error_source']])
        with self.request('/i18n.json') as response:
            self.assertIn('application/json',response.headers['Content-Type'])
            self.assertEqual(set(json.load(response)),{'en','pt','es'})

    def test_markup_and_script_have_no_external_assets(self):
        with self.request('/') as response:
            self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
            self.assertIn('SheetKeeper',response.read().decode())
        with self.request('/app.js') as response:
            self.assertNotIn('innerHTML',response.read().decode())

    def test_deployment_status_is_explicitly_server_configuration(self):
        with patch.dict(os.environ, {'SHEETKEEPER_DEPLOYMENT_PROVIDER': ''}):
            with self.request('/api/status') as response:
                status = json.load(response)
            self.assertFalse(status['cloud_deployed'])
            self.assertEqual(status['stage'], 'preparation')
        with patch.dict(os.environ, {'SHEETKEEPER_DEPLOYMENT_PROVIDER': 'vultr'}):
            with self.request('/api/status') as response:
                status = json.load(response)
            self.assertTrue(status['cloud_deployed'])
            self.assertEqual(status['deployment_claim_source'], 'server_configuration')
            self.assertIn('inference_budget', status)


if __name__=='__main__': unittest.main()
