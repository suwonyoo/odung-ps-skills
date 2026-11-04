import argparse
import contextlib
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import harness as h
import workflow as w
import coordination as c
from fixtures import intake, build_ready, verify_phase, assess_clear


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.out=contextlib.redirect_stdout(io.StringIO());self.out.__enter__()
        w.start(self.root,180)
        (self.root/'app.py').write_text('VALUE=3\n')
        self.task={'schema_version':1,'title':'Synthetic workflow','requirements':[{'id':'R1','description':'Return three','acceptance':'Value equals three','required':True}],
            'deliverables':[{'path':'app.py','purpose':'CLI source','required':True}],
            'checks':[{'id':'value','description':'Integer output','argv':[sys.executable,'-c','import app; assert app.VALUE==3'],'cwd':'.','timeout_seconds':5,'requirements':['R1'],'expected':'Three'}],'manual_checks':[]}
        h.write_json(w.path(self.root,'task.json'),self.task)

    def tearDown(self):
        self.out.__exit__(None,None,None);self.tmp.cleanup()

    def ask(self,id='Q1',**kw):
        d=dict(action='ask',id=id,text='Are adjacent intervals allowed?',impact='Overlap predicate',assumption='Block dependent work',blocks=['core'],requires=[],nonblocking=False);d.update(kw)
        return w.question(self.root,argparse.Namespace(**d))

    def answer(self,id='Q1',text='Yes, endpoint equality is allowed.'):
        p=self.root/(id+'.txt');p.write_text(text)
        return w.question(self.root,argparse.Namespace(action='answer',id=id,file=p.name))

    def resolve(self,id='Q1',changed=False):
        if w.read_state(self.root)['questions'][id]['status'] == 'answered':
            assess_clear(self.root, id)
        return w.question(self.root,argparse.Namespace(action='resolve',id=id,interpretation='Use half-open intervals; recorded for the synthetic test.',changed=changed,updates=['.harness/work/intake.json'],checks=['value']))

    def test_incomplete_first_analysis_cannot_advance(self):
        with self.assertRaises(h.KitError):w.event(self.root,'inputs-reviewed','guessed')
        self.assertEqual(w.read_state(self.root)['phase'],'intake')
        with self.assertRaises(h.KitError):w.select(self.root,'baseline','x','y','z')

    def test_no_dm_mode_persists_without_resetting_clock_or_creating_questions(self):
        before=w.read_state(self.root)['deadline']
        w.contact(self.root,'none','User says no stakeholder DM exists')
        w.start(self.root,210)
        state=w.read_state(self.root)
        self.assertEqual(state['contact']['mode'],'none')
        self.assertEqual(state['deadline'],before)
        self.assertEqual(state['questions'],{})
        self.assertIsNone(state['paused'])
        self.assertIn('담당자 DM: 없음',w.render(self.root))

    def test_no_dm_mode_does_not_silently_clear_a_pending_hard_rule(self):
        self.ask()
        w.contact(self.root,'none','No external contact is available')
        state=w.read_state(self.root)
        self.assertEqual(state['questions']['Q1']['status'],'pending')
        self.assertIsNotNone(state['paused'])
        self.assertIn('DM 요청 없이',state['next_action'])
        with self.assertRaises(h.KitError):w.resume(self.root,'skip without a decision')

    def test_no_dm_user_decision_is_not_attributed_to_hr(self):
        verify_phase(self.root)
        w.contact(self.root,'none','No DM')
        self.ask();self.answer(text='I choose half-open intervals for this local task.')
        self.resolve();w.resume(self.root,'User decision applied')
        state=w.read_state(self.root)
        self.assertEqual(state['phase'],'verify')
        self.assertEqual(state['questions']['Q1']['answers'][0]['actor'],'user-decision')
        notes=w.path(self.root,'questions.md').read_text()
        self.assertIn('사용자 결정 (담당자 확인 아님)',notes)
        self.assertNotIn('user-copied-hr',notes)

    def test_document_answer_changes_model_without_inventing_external_reply(self):
        verify_phase(self.root);h.check_command(self.root,[])
        w.contact(self.root,'none','No DM');self.ask()
        (self.root/'rule.txt').write_text('Intervals are half open.')
        w.question(self.root,argparse.Namespace(action='answer',id='Q1',file='rule.txt',source='provided-document'))
        self.resolve(changed=True);w.resume(self.root,'Supplied document reconciled')
        state=w.read_state(self.root)
        self.assertEqual(state['questions']['Q1']['answers'][0]['actor'],'provided-document')
        self.assertEqual(state['phase'],'modeling')
        self.assertEqual(h.audit_result(self.root)['checks'][0]['state'],'stale')

    def test_contact_availability_alone_does_not_change_semantic_evidence(self):
        verify_phase(self.root);h.check_command(self.root,[])
        w.contact(self.root,'none','No external contact')
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])
        w.contact(self.root,'manual','Contact became available')
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])

    def test_unknown_answer_source_cannot_mutate_question(self):
        self.ask();(self.root/'answer.txt').write_text('Invented answer')
        with self.assertRaises(h.KitError):
            w.question(self.root,argparse.Namespace(action='answer',id='Q1',file='answer.txt',source='invented'))
        self.assertEqual(w.read_state(self.root)['questions']['Q1']['answers'],[])

    def test_composite_model_requires_known_edges_and_coverage(self):
        d=intake(self.root)
        d['components'].append({'id':'C2','kind':'storage','decision':'Persist result','inputs':'C1 integer','outputs':'stored value','depends_on':['C1'],'requirement_ids':['R1']})
        d['composition']='Decision then storage, with a shared result version'
        d['couplings']=[{'from':'C1','to':'C2','shared':'version','handling':'compare version before write','loss':'no global optimization claim'}]
        h.write_json(w.path(self.root,'intake.json'),d)
        w.event(self.root,'inputs-reviewed','composite reviewed')
        self.assertEqual(w.read_state(self.root)['phase'],'modeling')
        d['components'][0]['depends_on']=['C2']
        h.write_json(w.path(self.root,'intake.json'),d)
        with self.assertRaisesRegex(h.KitError,'Cyclic'):w.event(self.root,'inputs-reviewed','cycle')

    def test_rule_check_must_cover_its_requirement(self):
        d=intake(self.root);d['rules'][0]['check_ids']=['missing']
        h.write_json(w.path(self.root,'intake.json'),d)
        with self.assertRaises(h.KitError):w.event(self.root,'inputs-reviewed','invalid check mapping')

    def test_material_source_change_requires_review(self):
        build_ready(self.root)
        (self.root/'BRIEF.md').write_text('New instruction')
        with self.assertRaises(h.KitError):w.event(self.root,'candidate-ready','old model')

    def test_phase_skip_and_changed_contract_are_rejected(self):
        with self.assertRaises(h.KitError):w.event(self.root,'integrated','skip')
        build_ready(self.root)
        p=w.path(self.root,'contract.json');d=h.load_json(p);d['output']='different';h.write_json(p,d)
        with self.assertRaises(h.KitError):w.event(self.root,'candidate-ready','silent change')

    def test_late_hr_pauses_only_dependent_execution_and_resume_restores_phase(self):
        verify_phase(self.root)
        self.ask()
        self.assertEqual(w.read_state(self.root)['paused']['phase'],'verify')
        with self.assertRaises(h.KitError):w.worker(self.root,'core','running','model',[],'work')
        w.worker(self.root,'ui','running','independent rendering',['ui'],'scaffold')
        with self.assertRaises(h.KitError):w.event(self.root,'verified','ignore HR')
        with self.assertRaises(h.KitError):w.resume(self.root,'no reply yet')
        self.answer();self.resolve();w.resume(self.root,'reconciled')
        self.assertEqual(w.read_state(self.root)['phase'],'verify')
        self.assertIsNone(w.read_state(self.root)['paused'])
        self.assertEqual(w.read_state(self.root)['questions']['Q1']['answers'][0]['text'],'Yes, endpoint equality is allowed.')

    def test_material_answer_returns_to_modeling_and_stales_evidence(self):
        verify_phase(self.root);h.check_command(self.root,[])
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])
        self.ask();self.answer();self.resolve(changed=True);w.resume(self.root,'rebuild model')
        self.assertEqual(w.read_state(self.root)['phase'],'modeling')
        self.assertIsNone(w.read_state(self.root)['contract_revision'])
        self.assertEqual(h.audit_result(self.root)['checks'][0]['state'],'stale')
        with self.assertRaises(h.KitError):w.event(self.root,'contract-ready','not re-reviewed')

    def test_conflicting_reply_preserves_original_and_cannot_resume(self):
        build_ready(self.root);self.ask();self.answer()
        w.question(self.root,argparse.Namespace(action='conflict',id='Q1',note='Conflicts with source S1'))
        with self.assertRaises(h.KitError):self.resolve()
        with self.assertRaises(h.KitError):w.resume(self.root,'ignore contradiction')
        self.answer(text='Corrected reply after source reconciliation.')
        self.assertEqual(len(w.read_state(self.root)['questions']['Q1']['answers']),2)

    def test_cannot_resolve_without_real_answer_or_unknown_check(self):
        intake(self.root);self.ask()
        with self.assertRaises(h.KitError):self.resolve()
        self.answer()
        assess_clear(self.root)
        with self.assertRaises(h.KitError):w.question(self.root,argparse.Namespace(action='resolve',id='Q1',interpretation='x',changed=False,updates=['BRIEF.md'],checks=['invented']))

    def test_unsettled_prerequisite_question_is_not_in_ready_frontier(self):
        self.ask()
        with self.assertRaises(h.KitError):self.ask('Q2',requires=['Q1'])

    def test_nonblocking_unknown_is_visible_without_stopping_independent_work(self):
        intake(self.root);self.ask(nonblocking=True,blocks=[],assumption='AI default: table rows sorted by ID; cosmetic only')
        self.assertIsNone(w.read_state(self.root)['paused'])
        w.worker(self.root,'core','running','core',[],'work')
        self.assertIn('Q1',w.render(self.root))

    def test_model_notes_change_invalidates_acceptance_without_clock_noise(self):
        verify_phase(self.root);h.check_command(self.root,[])
        w.render(self.root)
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])
        w.path(self.root,'model-spec.md').write_text('Changed constraint meaning')
        self.assertEqual(h.audit_result(self.root)['checks'][0]['state'],'stale')

    def test_undelivered_session_blocks_finish_even_when_tests_pass(self):
        verify_phase(self.root);w.worker(self.root,'core','waiting','handoff pending',[],'review');h.check_command(self.root,[])
        self.assertFalse(h.audit_result(self.root)['local_checks_satisfied'])
        w.worker(self.root,'core','done','handoff pending',[],'complete')
        w.event(self.root,'verified','actual current evidence')
        self.assertEqual(w.read_state(self.root)['phase'],'finish')

    def test_deadline_does_not_reset_and_no_new_command_can_exceed_it(self):
        s=w.read_state(self.root);s['deadline']=w.stamp(w.utc()-timedelta(seconds=1));h.write_json(w.path(self.root,'workflow.json'),s)
        w.start(self.root,180)
        with self.assertRaises(h.KitError):w.worker(self.root,'core','running','x',[],'y')
        self.assertIn('마감 경과',w.render(self.root))

    def test_live_lock_is_never_recovered_by_age(self):
        with w.locked(self.root):
            with self.assertRaises(h.KitError):w.recover_lock(self.root)
        h.write_json(w.path(self.root,'workflow.lock'),{'pid':12345,'host':w.platform.node(),'created_at':w.stamp()})
        with mock.patch.object(w.os,'kill',side_effect=ProcessLookupError):
            self.assertEqual(w.recover_lock(self.root),0)
        self.assertFalse(w.path(self.root,'workflow.lock').exists())

    def test_running_command_stops_when_hr_dependency_is_discovered(self):
        args=argparse.Namespace(argv=[sys.executable,'-c','import time;time.sleep(2)'],session='core',engine='baseline',label='long',limit=3,cwd='.',input=[])
        original=w.session_blockers;calls=[0]
        def later(state,session):
            calls[0]+=1
            return ['Q1'] if calls[0]>2 else []
        with mock.patch.object(w,'session_blockers',side_effect=later):
            result=w.timed_run(self.root,args)
        self.assertEqual(result,126)
        record=h.load_json(next(w.path(self.root,'runs').glob('*.json')))
        self.assertEqual(record['reason'],'hr_blocked')
        self.assertNotEqual(record['process_exit_code'],0)

    def test_postlaunch_bookkeeping_error_stops_child_and_preserves_exit(self):
        args=argparse.Namespace(argv=[sys.executable,'-c',"import time; from pathlib import Path; time.sleep(.3); Path('escaped').write_text('bad')"],session='core',engine='baseline',label='io-failure',limit=3,cwd='.',input=[])
        real=h.write_json;failed=[False]
        def inject(path,data,**kw):
            if path.parent.name=='runs' and data.get('child_pid') and not data.get('finished_at') and not failed[0]:
                failed[0]=True
                raise OSError('synthetic transient storage failure')
            return real(path,data,**kw)
        with mock.patch.object(h,'write_json',side_effect=inject):
            self.assertEqual(w.timed_run(self.root,args),125)
        record=h.load_json(next(w.path(self.root,'runs').glob('*.json')))
        self.assertEqual(record['reason'],'supervisor_error')
        self.assertLess(record['process_exit_code'],0)
        import time
        time.sleep(.4)
        self.assertFalse((self.root/'escaped').exists())

    def test_prelaunch_record_failure_does_not_lock_session(self):
        args=argparse.Namespace(argv=[sys.executable,'-c','pass'],session='core',engine='baseline',label='first',limit=3,cwd='.',input=[])
        w.path(self.root,'runs').write_text('parent collision')
        with self.assertRaises(OSError):w.timed_run(self.root,args)
        self.assertFalse(w.path(self.root,'workers/core.json').exists())
        w.path(self.root,'runs').unlink()
        self.assertEqual(w.timed_run(self.root,args),0)

    def test_ignored_build_deliverable_change_is_stale(self):
        (self.root/'dist').mkdir();artifact=self.root/'dist/result.txt';artifact.write_text('3')
        self.task['deliverables']=[{'path':'dist/result.txt','purpose':'Result artifact','required':True}]
        self.task['checks'][0]['argv']=[sys.executable,'-c',"from pathlib import Path; assert Path('dist/result.txt').read_text()=='3'"]
        h.write_json(w.path(self.root,'task.json'),self.task)
        verify_phase(self.root);h.check_command(self.root,[])
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])
        artifact.write_text('WRONG')
        self.assertEqual(h.audit_result(self.root)['checks'][0]['state'],'stale')
        self.assertFalse(h.audit_result(self.root)['local_checks_satisfied'])

    def test_acceptance_capture_failure_preserves_real_command_exit(self):
        self.task['checks'][0]['argv']=[sys.executable,'-c',"from pathlib import Path; Path('bad-link').symlink_to('/tmp'); raise SystemExit(7)"]
        h.write_json(w.path(self.root,'task.json'),self.task)
        self.assertEqual(h.check_command(self.root,[]),7)
        record=h.load_json(next(w.path(self.root,'evidence').glob('*.json')))
        self.assertEqual(record['process_exit_code'],7)
        self.assertIn('snapshot_error',record)
        self.assertTrue(record['workspace_changed'])

    def test_interrupted_acceptance_run_retains_failure_evidence(self):
        self.task['checks'][0]['argv']=[sys.executable,'-c','import time; time.sleep(2)']
        h.write_json(w.path(self.root,'task.json'),self.task)
        with mock.patch.object(h.time,'sleep',side_effect=KeyboardInterrupt):
            self.assertEqual(h.check_command(self.root,[]),130)
        record=h.load_json(next(w.path(self.root,'evidence').glob('*.json')))
        self.assertEqual(record['reason'],'interrupted')
        self.assertNotEqual(record['process_exit_code'],0)

    def test_abandoned_run_has_unknown_exit_and_can_be_retried(self):
        run_id='20261104T000000-acde'
        record={'id':run_id,'session':'core','engine':'baseline','label':'crashed','argv':['missing'],
                'cwd':'.','started_at':w.stamp(),'limit_seconds':5,'reason':'running','host':w.platform.node(),
                'supervisor_pid':12345,'child_pid':12346,'log':'.harness/work/runs/'+run_id+'.log'}
        h.write_json(w.path(self.root,'runs/'+run_id+'.json'),record)
        w.worker(self.root,'core','running','crashed',[],'pending',run_id=run_id)
        with mock.patch.object(w.os,'kill',side_effect=ProcessLookupError):w.recover_run(self.root,run_id,'Processes observed dead')
        final=h.load_json(w.path(self.root,'runs/'+run_id+'.json'))
        self.assertIsNone(final['exit_code']);self.assertEqual(final['reason'],'abandoned')
        self.assertIn('unknown',w.render(self.root))
        w.worker(self.root,'core','running','retry',[],'next')

if __name__=='__main__':unittest.main()
