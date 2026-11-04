import argparse
import contextlib
from datetime import timedelta
import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness as h
import workflow as w
import planning as p
import async_questions as aq
import coordination as c


def task(tid, session, minutes, deps=(), phase='parallel-build'):
    return dict(id=tid, title=tid, session=session, phase=phase, depends_on=list(deps),
                remaining_minutes=list(minutes), priority='required', status='pending',
                basis='Provisional estimate; no measurement yet', cut_if_late='Keep required behavior; remove optional polish')


def plan():
    return dict(schema_version=1, reserve_minutes=15, review_after_minutes=10,
                tasks=[task('A', 'lead', [5, 10], phase='intake'),
                       task('B', 'core', [25, 35], ['A']),
                       task('C', 'ui', [15, 30], ['A']),
                       task('D', 'lead', [5, 8], ['B', 'C'], phase='integrate'),
                       task('E', 'lead', [10, 15], ['D'], phase='verify')])


class PlanningAndInbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.out = contextlib.redirect_stdout(io.StringIO()); self.out.__enter__()
        w.start(self.root, 180)

    def tearDown(self):
        self.out.__exit__(None, None, None); self.tmp.cleanup()

    def set_plan(self, data=None):
        h.write_json(w.path(self.root, 'time-plan-input.json'), data or plan())
        return w.set_plan(self.root, '.harness/work/time-plan-input.json', 'Initial estimate or actual rework')

    def ask(self, qid='Q1', **kwargs):
        data = dict(action='ask', id=qid, text='May adjacent intervals touch?', impact='Boundary validator',
                    assumption='No dependent publication', blocks=['core'], requires=[], nonblocking=False)
        data.update(kwargs)
        w.question(self.root, argparse.Namespace(**data))

    def test_parallel_critical_path_and_single_owner_serialization(self):
        self.set_plan()
        result = p.summary(w.read_state(self.root), w.utc())
        self.assertEqual((result['low'], result['high']), (45, 68))
        serial = plan(); serial['tasks'][2]['session'] = 'core'
        self.set_plan(serial)
        result = p.summary(w.read_state(self.root), w.utc())
        self.assertEqual((result['low'], result['high']), (60, 98))

    def test_invalid_ranges_dependency_cycles_and_required_deferral_are_rejected(self):
        variants = []
        for bad in ([12, 3], [float('nan'), 8], [False, 8]):
            item = plan(); item['tasks'][0]['remaining_minutes'] = bad; variants.append(item)
        item = plan(); item['tasks'][0]['depends_on'] = ['E']; variants.append(item)
        item = plan(); item['tasks'][0].update(status='deferred', remaining_minutes=[0, 0]); variants.append(item)
        item = plan(); item['tasks'][0].update(priority='optional', status='deferred', remaining_minutes=[0, 0]); variants.append(item)
        for item in variants:
            with self.subTest(item=item):
                with self.assertRaises(h.KitError): self.set_plan(item)
        self.assertNotIn('time_plan', w.read_state(self.root))

    def test_replanning_preserves_deadline_pause_and_semantic_evidence(self):
        self.ask(); before = w.read_state(self.root)
        semantic = c.context_signature(self.root)
        self.set_plan(); self.set_plan()
        state = w.read_state(self.root)
        self.assertEqual(state['deadline'], before['deadline'])
        self.assertEqual(state['paused'], before['paused'])
        self.assertEqual(state['time_plan']['revision'], 2)
        self.assertEqual(c.context_signature(self.root), semantic)
        self.assertEqual(w.path(self.root, 'events.jsonl').read_text().count('"kind": "time-plan"'), 2)
        with self.assertRaises(h.KitError): w.resume(self.root, 'Budget adjusted only')

    def test_plan_review_after_elapsed_time_or_new_question_and_unknown_hr_wait(self):
        self.set_plan(); state = w.read_state(self.root)
        later = w.datetime.fromisoformat(state['time_plan']['at']) + timedelta(minutes=11)
        self.assertIn('정기 재산정 시점', p.summary(state, later)['review'])
        self.ask()
        state = w.read_state(self.root)
        self.assertIn('단계·질답·모델 변경', p.summary(state, w.utc())['review'])
        self.assertIn('대기시간 미상', '\n'.join(p.render(state, w.utc())))

    def test_overrun_is_visible_and_protected_time_is_configurable(self):
        self.set_plan(); state = w.read_state(self.root)
        deadline = w.datetime.fromisoformat(state['deadline'])
        result = p.summary(state, deadline - timedelta(minutes=70))
        self.assertLess(result['slack'], 0)
        self.assertIn('보수적 추정에서 예산 초과', result['review'])
        self.assertFalse(result['freeze_optional'])
        data = plan(); data['reserve_minutes'] = 5
        data['tasks'][-1]['remaining_minutes'] = [3, 7]
        self.set_plan(data); state = w.read_state(self.root)
        self.assertFalse(p.summary(state, deadline-timedelta(minutes=20))['freeze_optional'])
        self.assertTrue(p.summary(state, deadline-timedelta(minutes=12))['freeze_optional'])
        state['time_policy'] = {'mode':'flexible'}
        self.assertFalse(p.summary(state, deadline+timedelta(minutes=12))['freeze_optional'])

    def test_outbox_tracks_user_reported_delivery_and_never_edits_inbox(self):
        w.contact(self.root, 'manual', 'User will manually send DM')
        self.ask()
        outbox = w.path(self.root, 'hr-outbox.md')
        self.assertIn('Q1 · 전달 대기', outbox.read_text())
        inbox = w.path(self.root, 'hr-inbox.md'); inbox.write_text('User-owned raw notes')
        semantic = c.context_signature(self.root)
        w.question(self.root, argparse.Namespace(action='sent', id='Q1', note='User says sent in separate DM'))
        self.assertIn('Q1 · 답변 대기', outbox.read_text())
        self.assertEqual(inbox.read_text(), 'User-owned raw notes')
        self.assertEqual(c.context_signature(self.root), semantic)

    def test_batch_import_is_idempotent_keeps_raw_text_and_does_not_resume(self):
        self.ask(); self.ask('Q2', blocks=['integration'])
        inbox = w.path(self.root, 'hr-inbox.md')
        inbox.write_bytes('# 받은 원문\r\n\r\n## Q1\r\nYes.\r\n\r\n## Q2\r\nKeep the old plan.\r\nDo not publish stale data.\r\n'.encode('utf-8-sig'))
        self.assertIn('Q1, Q2', aq.inbox_status(self.root, w.read_state(self.root)))
        w.import_answers(self.root, '.harness/work/hr-inbox.md', 'user-copied-hr')
        state = w.read_state(self.root)
        self.assertEqual(state['questions']['Q1']['answers'][0]['text'], 'Yes.')
        self.assertEqual(state['questions']['Q2']['answers'][0]['text'], 'Keep the old plan.\r\nDo not publish stale data.')
        self.assertEqual(state['questions']['Q1']['status'], 'answered')
        self.assertIsNotNone(state['paused'])
        semantic = c.context_signature(self.root)
        w.import_answers(self.root, '.harness/work/hr-inbox.md', 'user-copied-hr')
        self.assertEqual(c.context_signature(self.root), semantic)
        self.assertEqual(len(w.read_state(self.root)['questions']['Q1']['answers']), 1)
        self.assertIn('새 원문 없음', aq.inbox_status(self.root, w.read_state(self.root)))
        with self.assertRaises(h.KitError): w.resume(self.root, 'Answer received but not applied')

    def test_batch_validation_has_no_partial_writes_or_silent_corrections(self):
        self.ask()
        inbox = w.path(self.root, 'hr-inbox.md')
        inbox.write_text('## Q1\nYes\n## Q404\nNo\n')
        with self.assertRaises(h.KitError): w.import_answers(self.root, '.harness/work/hr-inbox.md', 'user-copied-hr')
        self.assertEqual(w.read_state(self.root)['questions']['Q1']['answers'], [])
        inbox.write_text('## Q1\nYes\n')
        w.import_answers(self.root, '.harness/work/hr-inbox.md', 'user-copied-hr')
        inbox.write_text('## Q1\nNo\n')
        with self.assertRaises(h.KitError): w.import_answers(self.root, '.harness/work/hr-inbox.md', 'user-copied-hr')
        self.assertEqual(w.read_state(self.root)['questions']['Q1']['answers'][0]['text'], 'Yes')

    def test_inbox_handles_empty_sections_fenced_examples_and_duplicates(self):
        self.assertEqual(aq.parse('Example:\n```md\n## Q99\nExample only\n```\n## Q1\n\n'), {})
        self.assertEqual(aq.parse('## Q1\nReply\n```md\n## Q99\nLiteral reply\n```\n'), {'Q1': 'Reply\n```md\n## Q99\nLiteral reply\n```'})
        with self.assertRaises(h.KitError): aq.parse('## Q1\nA\n## Q1\nB\n')
        w.path(self.root, 'hr-inbox.md').write_bytes(b'\xff')
        self.assertIn('확인 필요', aq.inbox_status(self.root, w.read_state(self.root)))

    def test_no_dm_has_no_external_outbox_or_false_sent_record(self):
        w.contact(self.root, 'none', 'No external contact'); self.ask()
        self.assertNotIn('## Q1', w.path(self.root, 'hr-outbox.md').read_text())
        with self.assertRaises(h.KitError):
            w.question(self.root, argparse.Namespace(action='sent', id='Q1', note='AI guesses delivered'))

    def test_inbox_answer_wait_does_not_block_independent_command(self):
        self.ask()
        args = argparse.Namespace(argv=[sys.executable, '-c', 'print("independent")'], session='ui', engine='baseline', label='independent check', limit=2, cwd='.', input=[])
        self.assertEqual(w.timed_run(self.root, args), 0)
        args.session = 'core'
        with self.assertRaises(h.KitError): w.timed_run(self.root, args)


if __name__ == '__main__':
    unittest.main()
