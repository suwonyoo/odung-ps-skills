"""Structural intake and readiness checks. These do not infer business meaning."""
from pathlib import Path
import json

try:
    import harness as h
except ModuleNotFoundError:
    import runner as h


def workfile(root, name):
    return h.safe_path(root, '.harness/work/' + name)


def identified(items, label):
    if not isinstance(items, list):
        raise h.KitError(label + ' must be an array')
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not h.ID_RE.fullmatch(item['id']):
            raise h.KitError(label + ' needs valid IDs')
        if item['id'] in result:
            raise h.KitError(label + ' duplicate ID: ' + item['id'])
        result[item['id']] = item
    return result


def refs(value, known, label, *, empty=False):
    if not isinstance(value, list) or (not value and not empty) or any(not isinstance(x, str) or x not in known for x in value):
        raise h.KitError(label + ' must reference known IDs')
    if len(value) != len(set(value)):
        raise h.KitError(label + ' has duplicate references')


def text_fields(item, fields, label):
    if not isinstance(item, dict):
        raise h.KitError(label + ' must be an object')
    for field in fields:
        h.nonempty_string(item.get(field), label + '.' + field)


def intake_check(root, state):
    """Fail on omissions, broken references and impossible execution ordering."""
    task = h.validate_task(root)
    data = h.load_json(workfile(root, 'intake.json'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise h.KitError('intake.json needs schema_version=1')
    text_fields(data, ('goal', 'composition', 'out_of_scope'), 'intake')
    sources = identified(data.get('sources'), 'sources')
    components = identified(data.get('components'), 'components')
    rules = identified(data.get('rules'), 'rules')
    if not sources or not components or not rules:
        raise h.KitError('Intake needs actual sources, components and rules')
    hashes = {}
    for sid, source in sources.items():
        text_fields(source, ('path', 'locator', 'role'), 'source ' + sid)
        file = h.safe_path(root, source['path'])
        if not file.is_file():
            raise h.KitError('Missing source file: ' + source['path'])
        hashes[source['path']] = h.digest_file(file)
    req_ids = {r['id'] for r in task['requirements']}
    check_ids = {c['id'] for c in task['checks'] + task['manual_checks']}
    covered = set()
    for cid, component in components.items():
        text_fields(component, ('kind', 'decision', 'inputs', 'outputs'), 'component ' + cid)
        refs(component.get('requirement_ids'), req_ids, 'component requirements')
        refs(component.get('depends_on'), components, 'component dependencies', empty=True)
        covered.update(component['requirement_ids'])
    if req_ids - covered:
        raise h.KitError('Requirements missing from decomposition: ' + ', '.join(sorted(req_ids-covered)))
    visiting, done = set(), set()
    def visit(cid):
        if cid in visiting:
            raise h.KitError('Cyclic execution dependency: combine coupled decisions into one component, and describe coupling')
        if cid in done:
            return
        visiting.add(cid)
        for dep in components[cid]['depends_on']:
            visit(dep)
        visiting.remove(cid); done.add(cid)
    for cid in components:
        visit(cid)
    couplings = data.get('couplings')
    if not isinstance(couplings, list):
        raise h.KitError('couplings must be an array (explain independence in composition when empty)')
    for coupling in couplings:
        text_fields(coupling, ('from', 'to', 'shared', 'handling', 'loss'), 'coupling')
        if coupling['from'] not in components or coupling['to'] not in components:
            raise h.KitError('Coupling references unknown component')
    rule_coverage = set()
    for rid, rule in rules.items():
        text_fields(rule, ('meaning', 'source'), 'rule ' + rid)
        if rule['source'] not in sources or rule.get('type') not in ('hard', 'soft', 'behavior'):
            raise h.KitError('Rule needs a known source and hard/soft/behavior type')
        refs(rule.get('requirement_ids'), req_ids, 'rule requirements')
        refs(rule.get('check_ids'), check_ids, 'rule checks')
        mapped = {r for check in task['checks'] + task['manual_checks'] if check['id'] in rule['check_ids'] for r in check['requirements']}
        if not set(rule['requirement_ids']) <= mapped:
            raise h.KitError('Rule checks do not cover its requirement IDs')
        rule_coverage.update(rule['requirement_ids'])
    if req_ids - rule_coverage:
        raise h.KitError('Requirements without sourced rules: ' + ', '.join(sorted(req_ids-rule_coverage)))
    for section, fields in {
        'data_review': ('keys', 'joins', 'units', 'time', 'missing', 'duplicates', 'scale'),
        'objective': ('order', 'tradeoffs'),
        'delivery': ('run_command', 'submission_method'),
        'baseline': ('method', 'feasibility', 'check'),
        'model_size': ('estimate', 'growth_risk', 'reduction'),
        'next_slice': ('behavior', 'check'),
    }.items():
        text_fields(data.get(section), fields, section)
    unknowns = data.get('unknowns')
    if not isinstance(unknowns, list):
        raise h.KitError('unknowns must be an array')
    questions = state.get('questions', {})
    for unknown in unknowns:
        text_fields(unknown, ('question_id', 'impact', 'assumption'), 'unknown')
        if unknown['question_id'] not in questions:
            raise h.KitError('Unknown must reference a recorded question')
    return {'intake_sha256': h.digest_file(workfile(root, 'intake.json')),
            'task_sha256': h.digest_file(workfile(root, 'task.json')), 'sources': hashes}


def blockers(state):
    return [q for q in state.get('questions', {}).values() if q['blocking'] and q['status'] != 'resolved']


def current_intake(root, state):
    review = state.get('intake_review')
    if not review:
        raise h.KitError('Intake review missing; complete intake.json and event inputs-reviewed')
    if intake_check(root, state) != review:
        raise h.KitError('Intake/source/task changed; review inputs again before advancing')


def contract_signature(root):
    return h.digest_file(workfile(root, 'contract.json'))


def current_contract(root, state):
    if not state.get('contract_revision') or state.get('contract_sha256') != contract_signature(root):
        raise h.KitError('Contract is missing or changed; return to modeling and freeze a new revision')


def readiness_errors(root):
    file = workfile(root, 'workflow.json')
    if not file.exists():
        return []  # The standalone acceptance runner remains usable.
    state = h.load_json(file)
    errors = []
    if state.get('schema_version') != 2:
        return ['Unsupported workflow schema; use a fresh v3 task workspace']
    errors += ['Pending decision: ' + q['id'] for q in blockers(state)]
    if state.get('paused'):
        errors.append('Workflow paused; use resume after reconciling answers')
    for check in (current_intake, current_contract):
        try:
            check(root, state)
        except (h.KitError, OSError) as exc:
            errors.append(str(exc))
    for file in workfile(root, 'workers').glob('*.json'):
        worker = h.load_json(file)
        if worker.get('status') != 'done':
            errors.append('Session not done: ' + worker.get('id', file.stem))
    return errors


def context_signature(root):
    """Evidence depends on semantic records, never the clock/status/events."""
    files = {}
    for name in ('intake.json', 'contract.json', 'model-spec.md'):
        file = workfile(root, name)
        if file.exists():
            files[name] = h.digest_file(file)
    statefile = workfile(root, 'workflow.json')
    if statefile.exists():
        state = h.load_json(statefile)
        files['semantics'] = {key: state.get(key) for key in ('questions', 'model_revision', 'engine')}
        files['semantics']['questions'] = {qid: {k: v for k, v in q.items() if k != 'delivery'}
                                          for qid, q in state.get('questions', {}).items()}
    return h.digest_bytes(json.dumps(files, sort_keys=True, ensure_ascii=False).encode())
