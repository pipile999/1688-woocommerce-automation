"""Offline isolation tests: no product inputs, secrets or real HTTP calls."""
import ast, importlib.util, importlib, json, os, sys, unittest, subprocess
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0,'D:/codex/tools/site-runner-libs')
ROOTS = [Path(p) for p in sys.argv[1:]]
sys.argv=sys.argv[:1]
MODULES=[]
for i,root in enumerate(ROOTS):
    spec=importlib.util.spec_from_file_location('site'+str(i),root/'app/__init__.py',submodule_search_locations=[str(root/'app')])
    pkg=importlib.util.module_from_spec(spec);sys.modules[spec.name]=pkg;spec.loader.exec_module(pkg)
    MODULES.append(importlib.import_module(spec.name+'.site_guard'))

class IsolationTests(unittest.TestCase):
    def test_real_cli_cross_calls_and_parameter_override(self):
        for i,g in enumerate(MODULES):
            env={'SystemRoot':os.environ.get('SystemRoot','C:/Windows'),'WOOCOMMERCE_URL':MODULES[1-i].DOMAIN}
            out=subprocess.run([sys.executable,'-X','utf8',str(g.ROOT/'runner.py'),'--dry-run'],env=env,capture_output=True,text=True)
            self.assertEqual(out.returncode,2)
            self.assertIn('HARD STOP',out.stdout)
            env['WOOCOMMERCE_URL']=g.DOMAIN
            out=subprocess.run([sys.executable,'-X','utf8',str(g.ROOT/'runner.py'),'--dry-run','--root',str(MODULES[1-i].ROOT)],env=env,capture_output=True,text=True)
            self.assertNotEqual(out.returncode,0)

    def test_correct_sites_without_credentials_or_network(self):
        with patch('socket.socket',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('dotenv.dotenv_values',side_effect=AssertionError('CREDENTIAL_READ_FORBIDDEN')):
            for g in MODULES:
                self.assertEqual(g.preflight()['site_url'],g.DOMAIN)

    def test_cross_call_hard_stop(self):
        for i,g in enumerate(MODULES):
            wrong=MODULES[1-i].DOMAIN
            with self.assertRaisesRegex(ValueError,'HARD STOP'):g.assert_site(wrong)
            with patch.dict(os.environ,{'WOOCOMMERCE_URL':wrong}):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.preflight()

    def test_no_url_tricks(self):
        for g in MODULES:
            for url in (g.DOMAIN+'/',g.DOMAIN+'.invalid',g.DOMAIN+'/wp-json',g.DOMAIN.replace('https:','http:'),g.DOMAIN+'?x=1',g.DOMAIN+':443'):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.assert_site(url)

    def test_all_data_paths_disjoint(self):
        a,b=MODULES
        ap={str((a.ROOT/p).resolve()).casefold() for p in a.PATHS.values()}
        bp={str((b.ROOT/p).resolve()).casefold() for p in b.PATHS.values()}
        self.assertFalse(ap & bp)
        for g in MODULES:
            for rel in g.PATHS.values():self.assertTrue(g.contained(g.ROOT/rel).resolve().is_relative_to(g.ROOT.resolve()))
        self.assertNotEqual((a.ROOT/'.env').stat().st_ino,(b.ROOT/'.env').stat().st_ino)

    def test_cross_paths_and_traversal(self):
        for i,g in enumerate(MODULES):
            for p in (MODULES[1-i].ROOT/'data/keyword-map.json',g.ROOT/'../escape',g.ROOT.parent.parent/'.env'):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.contained(p)

    def test_profile_cannot_override_site(self):
        for i,g in enumerate(MODULES):
            with patch.object(g.json,'loads',return_value={'site':g.SITE,'site_url':MODULES[1-i].DOMAIN,'skill':g.SKILL}):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.preflight()

    def test_product_endpoint_allowlist(self):
        for g in MODULES:
            for path in ('products','products/12','products/12/variations','products/categories'):
                g.endpoint(g.DOMAIN,'wc','POST',path)
            for path in ('templates','settings','pages','../products','products/12?redirect=x','products/batch','https://other.invalid'):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.endpoint(g.DOMAIN,'wc','POST',path)
            for path in ('templates/1','pages/1','plugins','product/1'):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):g.endpoint(g.DOMAIN,'wp','POST',path)

    def test_runner_rejects_root_and_checkpoint_override(self):
        for i,g in enumerate(MODULES):
            runner=importlib.import_module('site'+str(i)+'.auto_import_runner').Runner
            with patch('dotenv.dotenv_values',side_effect=AssertionError('CREDENTIAL_READ_FORBIDDEN')):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):runner(MODULES[1-i].ROOT,dry_run=True)
                with self.assertRaisesRegex(ValueError,'HARD STOP'):runner(g.ROOT,dry_run=True,run_dir=MODULES[1-i].ROOT/'output')
                with patch('socket.socket',side_effect=AssertionError('NETWORK_FORBIDDEN')):
                    instance=runner(g.ROOT,dry_run=True)
                    self.assertTrue(instance.run_dir.is_relative_to(g.ROOT))
                    self.assertIsNone(instance.store)

    def test_http_client_rechecks_domain_and_redirect(self):
        for i,g in enumerate(MODULES):
            mod=importlib.import_module('site'+str(i)+'.woocommerce')
            client=mod.WooCommerceClient.__new__(mod.WooCommerceClient)
            client.base_url=MODULES[1-i].DOMAIN
            with patch.object(mod.requests,'request',side_effect=AssertionError('NETWORK_FORBIDDEN')):
                with self.assertRaisesRegex(ValueError,'HARD STOP'):client._request('GET','products')
            client.base_url=g.DOMAIN;client.key='synthetic';client.secret='synthetic'
            response=Mock(status_code=302)
            with patch.object(mod.requests,'request',return_value=response) as request:
                with self.assertRaisesRegex(ValueError,'HARD STOP'):client._request('GET','products')
                self.assertFalse(request.call_args.kwargs['allow_redirects'])

    def test_all_python_syntax(self):
        for root in ROOTS:
            for path in root.rglob('*.py'):ast.parse(path.read_text(encoding='utf8'),filename=str(path))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IsolationTests))
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'credentials_read':False,'product_operations':0,'real_http_calls':0,'paths':[{**g.preflight()} for g in MODULES]}
    Path(__file__).with_name('site-isolation-test-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
