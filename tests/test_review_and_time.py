"""Synthetic ambiguity, pre-solve and flexible-time regression scenarios."""
import argparse
import contextlib
from datetime import timedelta
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness as h
import workflow as w
import specification as spec
import coordination as c
from fixtures import intake, model_review, verify_phase


class ReviewAndTime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__()
        w.start(self.root)
        (self.root / 'app.py').write_text('VALUE=3\n')
        h.write_json(w.path(self.root, 'task.json'), {
            'schema_version':1, 'title':'Synthetic review',
            'requirements':[{'id':'R1','description':'Three','acceptance':'Exact integer three','required':True}],
            'deliverables':[{'path':'app.py','purpose':'CLI','required':True}],
            'checks':[{'id':'value','description':'Value','argv':[sys.executable,'-c','import app; assert app.VALUE==3'],
                       'cwd':'.','timeout_seconds':3,'requirements':['R1'],'expected':'Three'}], 'manual_checks':[]})

    def tearDown(self):
        self.output.__exit__(None, None, None); self.tmp.cleanup()

    def modeling(self, engine='baseline'):
        intake(self.root)
        w.event(self.root, 'inputs-reviewed', 'Read real synthetic source')
        w.select(self.root, engine, 'Synthetic choice', 'Alternative recorded', 'No actual solver installed in this test')

    def runargs(self, **kw):
        data = dict(argv=[sys.executable, '-c', 'print(3)'], session='core', engine='baseline',
                    label='synthetic command', limit=2, cwd='.', input=[], purpose='solve')
        data.update(kw)
        return argparse.Namespace(**data)

    def ask(self, **kw):
        data = dict(action='ask', id='Q1', text='Does the cap apply per person or to the average?',
                    impact='Different validity of the plan', assumption='Do not invent a threshold',
                    blocks=['core'], requires=[], nonblocking=False, kind='business-rule')
        data.update(kw)
        w.question(self.root, argparse.Namespace(**data))

    def answer(self, text, filename='reply.txt'):
        (self.root / filename).write_text(text)
        w.question(self.root, argparse.Namespace(action='answer', id='Q1', file=filename, source='user-copied-hr'))

    def assess(self, verdict='clear'):
        w.question(self.root, argparse.Namespace(action='assess', id='Q1', verdict=verdict,
                   meaning='Cap applies to each person.' if verdict == 'clear' else 'Preference is known, cap is not.',
                   example='One person 31 minutes and one 29; cap 30', expected='Reject; average is not enough',
                   remaining='Per-person scope and exact cap', followup='Are 31 and 29 minutes allowed when the average is 30?'))

    def resolve(self):
        w.question(self.root, argparse.Namespace(action='resolve', id='Q1', interpretation='Each person must be within the cap',
                   changed=False, updates=['.harness/work/intake.json'], checks=['value']))

    def test_vague_reply_cannot_resolve_or_reassess_without_new_evidence(self):
        self.modeling(); w.contact(self.root, 'manual', 'User operates DM'); self.ask()
        self.answer('가능한 한 짧게, 상황에 따라 적절히 해 주세요.')
        with self.assertRaisesRegex(h.KitError, 'Assess answer clarity'): self.resolve()
        self.assess('ambiguous')
        q = w.read_state(self.root)['questions']['Q1']
        self.assertEqual(q['status'], 'needs-clarification')
        self.assertIn('31 and 29', w.path(self.root, 'hr-outbox.md').read_text())
        for action in (self.resolve, lambda:self.assess(), lambda:w.resume(self.root, 'No new reply'),
                       lambda:w.timed_run(self.root, self.runargs(session='renamed'))):
            with self.assertRaises(h.KitError): action()
        self.assertEqual(w.timed_run(self.root, self.runargs(session='ui', purpose='utility')), 0)
        self.answer('Each person must be at most 30 minutes, including exactly 30.', 'clarification.txt')
        self.assertNotIn('assessment', w.read_state(self.root)['questions']['Q1'])
        with self.assertRaises(h.KitError): self.resolve()
        self.assess(); self.resolve(); w.resume(self.root, 'Concrete clarification applied')
        model_review(self.root)
        self.assertEqual(w.timed_run(self.root, self.runargs()), 0)
        q = w.read_state(self.root)['questions']['Q1']
        self.assertEqual(len(q['answers']), 2)
        self.assertEqual([a['verdict'] for a in q['assessments']], ['ambiguous', 'clear'])
        self.assertIn('가능한 한', w.path(self.root, 'questions.md').read_text())

    def test_partial_and_conflicting_answers_stay_blocked(self):
        self.modeling(); self.ask(); self.answer('Some cases may be allowed.')
        self.assess('partial')
        with self.assertRaises(h.KitError): self.resolve()
        self.answer('The instructions conflict with my earlier reply.', 'second.txt')
        self.assess('conflicting')
        self.assertEqual(w.read_state(self.root)['questions']['Q1']['status'], 'conflict')
        with self.assertRaises(h.KitError): w.review_model(self.root, 'Ignore contradiction')

    def test_delegation_is_limited_to_implementation_choices(self):
        self.modeling(); self.ask(); self.answer('Use your recommendation.')
        with self.assertRaisesRegex(h.KitError, 'Delegation'): self.assess('delegated')
        self.assertNotIn('assessment', w.read_state(self.root)['questions']['Q1'])
        self.ask(id='Q2', kind='implementation', text='Sort table rows by ID?', impact='Display order only',
                 assumption='Reversible sort preference', blocks=[], nonblocking=True)
        (self.root / 'sort.txt').write_text('Use ID sorting as recommended.')
        w.question(self.root, argparse.Namespace(action='answer', id='Q2', file='sort.txt', source='user-decision'))
        w.question(self.root, argparse.Namespace(action='assess', id='Q2', verdict='delegated', meaning='Sort by ID',
                   example='B,A input rows', expected='A,B on screen'))
        self.assertTrue(spec.answer_ready(w.read_state(self.root)['questions']['Q2']))

    def test_new_reply_after_conflict_cannot_reuse_old_clear_assessment(self):
        self.modeling(); self.ask(); self.answer('Every person at most 30.'); self.assess()
        w.question(self.root, argparse.Namespace(action='conflict', id='Q1', note='Formal brief differs'))
        self.answer('The formal brief governs.', 'new.txt')
        with self.assertRaisesRegex(h.KitError, 'Assess answer clarity'): self.resolve()

    def test_unreviewed_solver_cannot_launch_even_with_a_new_session_name(self):
        self.modeling('ortools-cp-sat')
        args = self.runargs(engine='ortools-cp-sat', session='unrelated', argv=[sys.executable, '-c', "open('sentinel','w').write('ran')"])
        with self.assertRaisesRegex(h.KitError, 'review missing'): w.timed_run(self.root, args)
        self.assertFalse((self.root / 'sentinel').exists())
        args.purpose = 'utility'
        with self.assertRaises(h.KitError): w.timed_run(self.root, args)
        args.purpose = 'solve'; model_review(self.root)
        self.assertEqual(w.timed_run(self.root, args), 0)

    def test_review_requires_rule_coverage_and_boundary_result(self):
        self.modeling(); model_review(self.root)
        file = w.path(self.root, 'spec-review.json'); original = h.load_json(file)
        for change in ('missing_rule', 'missing_boundary'):
            import copy
            data = copy.deepcopy(original)
            if change == 'missing_rule': data['rules'] = []
            else: data['rules'][0]['boundary_expected'] = ''
            h.write_json(file, data)
            with self.assertRaises(h.KitError): w.review_model(self.root, 'Incomplete')

    def test_new_business_question_stops_a_running_solve_in_a_different_session(self):
        self.modeling(); model_review(self.root)
        original = w.subprocess.Popen
        def launch(*args, **kw):
            child = original(*args, **kw)
            self.ask(blocks=['core'])
            return child
        args = self.runargs(session='renamed-solver', argv=[sys.executable, '-c', 'import time; time.sleep(2)'])
        with mock.patch.object(w.subprocess, 'Popen', side_effect=launch):
            self.assertEqual(w.timed_run(self.root, args), 126)
        run = h.load_json(next(w.path(self.root, 'runs').glob('*.json')))
        self.assertEqual(run['reason'], 'hr_blocked')
        self.assertNotEqual(run['process_exit_code'], 0)

    def test_review_cannot_omit_a_reconciled_blocking_question(self):
        self.modeling(); self.ask(); self.answer('Every person at most 30 minutes.'); self.assess()
        self.resolve(); w.resume(self.root, 'Actual answer applied'); model_review(self.root)
        file = w.path(self.root, 'spec-review.json'); data = h.load_json(file)
        data['hr']['question_ids'] = []
        h.write_json(file, data)
        with self.assertRaisesRegex(h.KitError, 'omits blocking'): w.review_model(self.root, 'Forgot decision')

    def test_review_stales_when_model_source_review_or_question_changes(self):
        self.modeling(); model_review(self.root)
        for name in ('model-spec.md', 'spec-review.json'):
            file = w.path(self.root, name); original = file.read_bytes()
            file.write_bytes(original + b'\n ')
            with self.assertRaisesRegex(h.KitError, 'stale'): w.timed_run(self.root, self.runargs())
            file.write_bytes(original)
        brief = self.root / 'BRIEF.md'; original = brief.read_text(); brief.write_text(original+' Updated.')
        with self.assertRaises(h.KitError): w.timed_run(self.root, self.runargs())
        brief.write_text(original)
        self.ask()
        with self.assertRaises(h.KitError): w.timed_run(self.root, self.runargs(session='another'))
        w.contact(self.root, 'none', 'DM unavailable now')
        with self.assertRaises(h.KitError): w.review_model(self.root, 'Skip HR')

    def test_default_target_can_overrun_without_blocking_bounded_work(self):
        state = w.read_state(self.root)
        self.assertFalse(w.fixed_time(state))
        state['deadline'] = w.stamp(w.utc()-timedelta(minutes=2))
        h.write_json(w.path(self.root, 'workflow.json'), state)
        self.assertEqual(w.timed_run(self.root, self.runargs(purpose='utility')), 0)
        self.assertIn('유연한 목표 경과', w.render(self.root))
        with self.assertRaisesRegex(h.KitError, 'actual --minutes'): w.start(self.root, time_mode='fixed')

    def test_flexible_schedule_revises_target_preserves_elapsed_and_evidence(self):
        verify_phase(self.root); h.check_command(self.root, [])
        before = w.read_state(self.root); signature = c.context_signature(self.root)
        w.schedule(self.root, 240, 'flexible', 'Required design discovered; scope-based estimate')
        state = w.read_state(self.root)
        self.assertEqual(state['started_at'], before['started_at'])
        self.assertNotEqual(state['deadline'], before['deadline'])
        self.assertEqual(signature, c.context_signature(self.root))
        self.assertTrue(h.audit_result(self.root)['local_checks_satisfied'])
        self.assertIn('Required design', w.path(self.root, 'events.jsonl').read_text())
        w.start(self.root, 1)
        self.assertEqual(w.read_state(self.root)['deadline'], state['deadline'])

    def test_real_deadline_cannot_be_changed_without_actual_instruction_file(self):
        (self.root / 'time.txt').write_text('User: actual limit is 60 minutes from now.')
        w.schedule(self.root, 60, 'fixed', 'Actual deadline supplied', 'time.txt')
        old = w.read_state(self.root)
        for mode in ('fixed', 'flexible'):
            with self.assertRaises(h.KitError): w.schedule(self.root, 120, mode, 'Design takes longer')
        self.assertEqual(w.read_state(self.root), old)
        with mock.patch.object(w, 'utc', return_value=w.datetime.fromisoformat(old['deadline'])+timedelta(seconds=1)):
            with self.assertRaises(h.KitError): w.timed_run(self.root, self.runargs(purpose='utility'))
        (self.root / 'extension.txt').write_text('User: no external deadline now; plan flexibly.')
        w.schedule(self.root, 120, 'flexible', 'User changed actual constraint', 'extension.txt')
        self.assertFalse(w.fixed_time(w.read_state(self.root)))

    def test_contact_and_transport_do_not_stale_a_review(self):
        self.modeling(); model_review(self.root)
        w.contact(self.root, 'none', 'No DM needed for exact source')
        spec.current(self.root, w.read_state(self.root))


if __name__ == '__main__':
    unittest.main()
