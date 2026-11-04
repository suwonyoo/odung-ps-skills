"""Require a current, traceable model review; do not infer business meaning."""
import json
from pathlib import Path

try:
    import harness as h
except ModuleNotFoundError:
    import runner as h
import coordination as c


def answer_ready(question):
    assessment = question.get('assessment', {})
    return (assessment.get('answer_count') == len(question.get('answers', []))
            and assessment.get('verdict') in ('clear', 'delegated')
            and all(assessment.get(k) for k in ('meaning', 'example', 'expected'))
            and (assessment['verdict'] != 'delegated' or question.get('kind') == 'implementation'))


def signature(root, state):
    c.current_intake(root, state)
    if not state.get('engine') or state.get('paused') or c.blockers(state):
        raise h.KitError('Model review needs a selected engine and reconciled blocking questions; resume first')
    review = h.load_json(c.workfile(root, 'spec-review.json'))
    if not isinstance(review, dict) or review.get('schema_version') != 1:
        raise h.KitError('spec-review.json needs schema_version=1')
    c.text_fields(review, ('objective', 'coupling', 'failure'), 'model review')
    intake = h.load_json(c.workfile(root, 'intake.json'))
    rules = c.identified(review.get('rules'), 'review rules')
    if set(rules) != {r['id'] for r in intake['rules']}:
        raise h.KitError('Model review must cover every intake rule exactly once')
    questions = state.get('questions', {})
    referenced = set()
    for rid, rule in rules.items():
        c.text_fields(rule, ('meaning', 'example', 'expected', 'boundary', 'boundary_expected'), rid)
        c.refs(rule.get('question_ids'), questions, 'rule questions', empty=True)
        referenced.update(rule['question_ids'])
    hr = review.get('hr')
    c.text_fields(hr, ('summary',), 'HR ambiguity review')
    c.refs(hr.get('question_ids'), questions, 'HR review questions', empty=True)
    referenced.update(hr['question_ids'])
    required = {q['id'] for q in questions.values() if q['blocking']}
    required.update(u['question_id'] for u in intake['unknowns'] if questions[u['question_id']]['blocking'])
    if required - referenced:
        raise h.KitError('Model review omits blocking decision history: ' + ', '.join(sorted(required-referenced)))
    for qid in referenced:
        if questions[qid]['status'] != 'resolved' or not answer_ready(questions[qid]):
            raise h.KitError('Model decision still needs a clear assessed answer and reconciliation: ' + qid)
    model = c.workfile(root, 'model-spec.md')
    text = model.read_text(encoding='utf-8')
    h.nonempty_string(text, 'model-spec.md')
    template = Path(__file__).resolve().parent / 'templates/model-spec.md'
    if text == template.read_text(encoding='utf-8'):
        raise h.KitError('Write the actual model specification before reviewing it')
    semantics = {qid: {k: v for k, v in q.items() if k != 'delivery'} for qid, q in questions.items()}
    value = {'intake': state['intake_review'], 'engine': state['engine'],
             'model_revision': state['model_revision'], 'questions': semantics,
             'model': h.digest_file(model), 'review': h.digest_file(c.workfile(root, 'spec-review.json'))}
    return h.digest_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def current(root, state):
    saved = state.get('model_review')
    if not saved:
        raise h.KitError('Pre-solve model/HR review missing; write spec-review.json and run review-model')
    if signature(root, state) != saved.get('signature'):
        raise h.KitError('Model/HR review is stale; reconcile changes and run review-model again')


def assess(question, args, at):
    if question['status'] != 'answered' or not question.get('answers'):
        raise h.KitError('Assess an actual new answer; clarification needs new evidence before reassessment')
    verdict = args.verdict
    if verdict not in ('clear', 'partial', 'ambiguous', 'conflicting', 'delegated'):
        raise h.KitError('Unknown answer quality verdict')
    h.nonempty_string(args.meaning, 'confirmed meaning or what remains unknown')
    record = {'verdict': verdict, 'meaning': args.meaning, 'at': at,
              'answer_count': len(question['answers'])}
    if verdict in ('clear', 'delegated'):
        if verdict == 'delegated' and question.get('kind') != 'implementation':
            raise h.KitError('Delegation cannot settle an unknown business rule')
        for field in ('example', 'expected'):
            h.nonempty_string(getattr(args, field, None), 'assessment.' + field)
            record[field] = getattr(args, field)
    else:
        for field in ('remaining', 'followup'):
            h.nonempty_string(getattr(args, field, None), 'assessment.' + field)
            record[field] = getattr(args, field)
    question['assessment'] = record
    question.setdefault('assessments', []).append(dict(record))
    if verdict not in ('clear', 'delegated'):
        question['status'] = 'conflict' if verdict == 'conflicting' else 'needs-clarification'
        question.pop('delivery', None)
