import copy
import json
import os
import stat
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import replay
import build_site

ROOT=Path(__file__).resolve().parent
NODE=__import__('shutil').which('node')

class HardeningTests(unittest.TestCase):
    def case(self):
        return replay.load_case(ROOT/'cases'/'missing-history.json')

    def test_strict_types_and_unsupported_fields(self):
        mutations=[('schema_version',True),('schema_version',1.0),('provenance',[]),('provenance',{}),('extra','uninterpreted')]
        for key,value in mutations:
            c=self.case();c[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(replay.CaseError):replay.validate_case(c)
        for value in [[],{},True,1,None]:
            c=self.case();c['initial']['outcome']['status']=value
            with self.subTest(value=value),self.assertRaises(replay.CaseError):replay.validate_case(c)

    def test_strict_json_and_unicode(self):
        for raw in [b'{"schema_version":1,"schema_version":1}',b'{"value":NaN}',b'\xff',b'['*2000+b']'*2000]:
            with self.subTest(raw=raw[:40]),self.assertRaises(replay.CaseError):replay.parse_case(raw)
        c=self.case();c['title']='bad\ud800'
        with self.assertRaises(replay.CaseError):replay.validate_case(c)

    def test_unseen_domain_has_no_fixture_specific_diagnosis(self):
        c=self.case();c['id']='unseen-random-id';c['title']='A new dispatch workflow'
        for a in ['initial','later']:
            c[a]['context']={'route':'north','payload_format':'v7'};c[a]['action']='dispatch {route:north}'
        c['correction']['intended_action']='dispatch {route:south}'
        self.assertEqual(replay.diagnose(c)['diagnosis'],'correction_unavailable')
        c['later']['context']['payload_format']='v8'
        self.assertEqual(replay.diagnose(c)['scope_differences'],['payload_format'])

    def test_absent_comparison_never_establishes_comparable_failure(self):
        c=self.case();del c['comparison'];r=replay.diagnose(c)
        self.assertEqual(r['diagnosis'],'comparability_unknown');self.assertFalse(r['declared_comparable_repeat_failure']);self.assertTrue(r['reported_failure_pattern'])

    def test_success_and_same_intended_action_have_distinct_conclusions(self):
        c=self.case();c['initial']['outcome']['status']='success'
        self.assertEqual(replay.diagnose(c)['diagnosis'],'initial_success')
        c=self.case();c['correction']['intended_action']=c['initial']['action']
        self.assertEqual(replay.diagnose(c)['diagnosis'],'correction_preserves_action')

    def test_markdown_payload_cannot_escape_fence(self):
        c=self.case();c['title']='![pixel](https://example.invalid/x)\n```\n<script>bad</script>\n``````'
        rendered=replay.markdown_report([replay.diagnose(c)])
        # Exactly one fenced payload, with a fence longer than any supplied run.
        self.assertEqual(rendered.count('```````'),2)
        self.assertTrue(rendered.endswith('```````\n'))

    def test_input_and_symlink_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'report.json';original=json.dumps(self.case()).encode();source.write_bytes(original)
            self.assertEqual(replay.main(['--input',str(source),'--output',folder]),2);self.assertEqual(source.read_bytes(),original)
            source=base/'source.json';source.write_bytes(original);(base/'report.json').unlink();(base/'report.json').symlink_to(source)
            self.assertEqual(replay.main(['--input',str(source),'--output',folder]),2);self.assertEqual(source.read_bytes(),original)

    def test_custom_input_requires_explicit_private_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.json';source.write_text(json.dumps(self.case()))
            self.assertEqual(replay.main(['--input',str(source)]),2)

    def test_html_exposes_correction_that_violates_supplied_guard(self):
        c=self.case();c['correction']['intended_action']=c['initial']['action']
        self.assertIn('correction action is outside.',replay.html_report([replay.diagnose(c)]))

    def test_unicode_blank_and_byte_limits(self):
        for title in ['\u0085','\ufeff','\ufeff \u0085']:
            c=self.case();c['title']=title
            with self.subTest(title=repr(title)),self.assertRaises(replay.CaseError):replay.validate_case(c)
        c=self.case();c['title']='界'*12000
        c['initial']['outcome']['evidence']='界'*12000;c['later']['outcome']['evidence']='界'*12000
        with self.assertRaisesRegex(replay.CaseError,'100 KB'):replay.parse_case(json.dumps(c,ensure_ascii=False))

    def test_existing_bundle_preserved_when_one_destination_is_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'report.json').write_text('old json');(p/'report.html').write_text('old html');(p/'report.md').mkdir()
            self.assertEqual(replay.main(['--output',folder]),2)
            self.assertEqual((p/'report.json').read_text(),'old json');self.assertEqual((p/'report.html').read_text(),'old html')

    def test_bundle_restored_after_replacement_error(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);old={'report.json':'old json','report.md':'old md','report.html':'old html'}
            for name,value in old.items():(p/name).write_text(value)
            real_replace=replay.os.replace;count=0
            def fail_second(source,target):
                nonlocal count
                count+=1
                if count==2:raise OSError('Synthetic second replacement failure')
                return real_replace(source,target)
            with mock.patch.object(replay.os,'replace',side_effect=fail_second),self.assertRaises(OSError):replay.write_bundle(p,{name:'new '+value for name,value in old.items()})
            self.assertEqual({name:(p/name).read_text() for name in old},old)

    def test_pathological_integer_is_a_controlled_parser_error(self):
        raw='{"schema_version":'+('9'*5000)+'}'
        with self.assertRaises(replay.CaseError):replay.parse_case(raw)
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'large-number.json';source.write_text(raw)
            done=subprocess.run([sys.executable,str(ROOT/'replay.py'),'--input',str(source),'--output',str(Path(folder)/'out')],capture_output=True,text=True,timeout=3)
            self.assertEqual(done.returncode,2);self.assertNotIn('Traceback',done.stderr)

    @unittest.skipUnless(hasattr(os,'mkfifo'),'Named pipes are POSIX-specific')
    def test_fifo_input_rejects_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            pipe=Path(folder)/'case.json';os.mkfifo(pipe);alias=Path(folder)/'alias.json';alias.symlink_to(pipe)
            for source in [pipe,alias]:
                done=subprocess.run([sys.executable,str(ROOT/'replay.py'),'--input',str(source),'--output',str(Path(folder)/'out')],capture_output=True,text=True,timeout=3)
                self.assertEqual(done.returncode,2);self.assertIn('regular local JSON file',done.stderr)
                self.assertNotIn('Traceback',done.stderr)

    def test_selected_bundled_case_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);cases=base/'cases';cases.mkdir();source=cases/'report.json';original=json.dumps(self.case());source.write_text(original)
            with mock.patch.object(replay,'ROOT',base):
                self.assertEqual(replay.main(['--case','all','--output',str(cases)]),2)
            self.assertEqual(source.read_text(),original)

    @unittest.skipUnless(os.name=='posix','POSIX file-mode test')
    def test_success_and_rollback_preserve_private_report_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);old={name:'private '+name for name in ['report.json','report.md','report.html']}
            for name,value in old.items():(base/name).write_text(value);os.chmod(base/name,0o600)
            replay.write_bundle(base,{name:'new '+value for name,value in old.items()})
            self.assertEqual([stat.S_IMODE((base/name).stat().st_mode) for name in old],[0o600]*3)
            before={name:(base/name).read_bytes() for name in old};real_replace=replay.os.replace;count=0
            def fail_second(source,target):
                nonlocal count
                count+=1
                if count==2:raise OSError('Synthetic replacement failure')
                return real_replace(source,target)
            with mock.patch.object(replay.os,'replace',side_effect=fail_second),self.assertRaises(OSError):replay.write_bundle(base,{name:'later '+value for name,value in old.items()})
            self.assertEqual({name:(base/name).read_bytes() for name in old},before)
            self.assertEqual([stat.S_IMODE((base/name).stat().st_mode) for name in old],[0o600]*3)
            os.chmod(base/'report.json',0o400);replay.write_bundle(base,{name:'final' for name in old})
            self.assertEqual(stat.S_IMODE((base/'report.json').stat().st_mode),0o400)

    def test_ascii_console_does_not_turn_success_into_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'input.json';c=self.case();c['id']='case-界';source.write_text(json.dumps(c))
            done=subprocess.run([sys.executable,str(ROOT/'replay.py'),'--input',str(source),'--output',str(base/'报告')],env=dict(os.environ,PYTHONIOENCODING='ascii:strict'),capture_output=True,text=True,timeout=3)
            self.assertEqual(done.returncode,0);self.assertNotIn('Traceback',done.stderr)
            self.assertTrue((base/'报告'/'report.json').is_file())

    def test_one_utf8_bom_has_consistent_size_and_parse_rules(self):
        raw=json.dumps(self.case());self.assertEqual(replay.parse_case('\ufeff'+raw),self.case());self.assertEqual(replay.parse_case(('\ufeff'+raw).encode()),self.case())
        with self.assertRaises(replay.CaseError):replay.parse_case('\ufeff\ufeff'+raw)
        if NODE:
            inputs=['\ufeff'+raw,'\ufeff\ufeff'+raw]
            program="const w=require('./web.js'),fs=require('fs');process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(s=>{try{w.parseCase(s);return true}catch{return false}})));"
            done=subprocess.run([NODE,'-e',program],input=json.dumps(inputs),capture_output=True,text=True,cwd=ROOT,check=True)
            self.assertEqual(json.loads(done.stdout),[True,False])

    def test_site_is_reproducible_and_no_unreviewed_network_code(self):
        self.assertEqual((ROOT/'docs/index.html').read_text(),build_site.build())
        js=(ROOT/'web.js').read_text()
        for code in ['fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage', '.innerHTML', 'eval(']:self.assertNotIn(code,js)
        self.assertIn("connect-src 'none'",__import__("html").unescape(build_site.build()))

    @unittest.skipUnless(NODE, "Node.js is needed for browser-state checks")
    def test_browser_file_state_and_download_recovery(self):
        done=subprocess.run([NODE,str(ROOT/'test_web_state.cjs')],cwd=ROOT,text=True,capture_output=True,timeout=15)
        self.assertEqual(done.returncode,0,done.stdout+'\n'+done.stderr)
        self.assertIn('state checks passed (mock DOM limits apply)',done.stdout)

    @unittest.skipUnless(NODE, "Node.js is needed only for cross-runtime tests")
    def test_browser_and_python_share_outputs_over_branch_matrix(self):
        cases=[]
        for first in ['failure','success','unknown']:
            for later in ['failure','success','unknown']:
                for visible in [True,False,None]:
                    for comparable in [True,False,None]:
                        for same in [True,False]:
                            c=self.case();c['initial']['outcome']['status']=first;c['later']['outcome']['status']=later;c['correction']['visible_to_later']=visible;c['comparison']['comparable']=comparable
                            if not same:c['later']['action']='new-action'
                            cases.append(c)
        for field in ['title','action','context','unicode_keys']:
            c=self.case()
            if field=='title':c[field]='安全 <script> 😀'
            elif field=='action':c['later'][field]='READ-REPLICA '
            elif field=='context':c['later'][field]={'new-domain':'arbitrary'}
            else:c['later']['context']={'\ue000':'private-use','😀':'astral'}
            cases.append(c)
        payload={'rules':replay.RULES,'cases':cases}
        program="const fs=require('fs'),w=require('./web.js'),p=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(p.cases.map(c=>w.analyze(w.parseCase(JSON.stringify(c)),p.rules))));"
        done=subprocess.run([NODE,'-e',program],input=json.dumps(payload),text=True,capture_output=True,cwd=ROOT,check=True)
        self.assertEqual(json.loads(done.stdout),[replay.diagnose(c) for c in cases])

if __name__=='__main__':unittest.main()
