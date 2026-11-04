"""Advisory remaining-work estimates; never an execution or correctness gate."""
from datetime import datetime
import json
import math

try:
    import harness as h
except ModuleNotFoundError:
    import runner as h
import coordination as c

PHASES = ('intake', 'modeling', 'parallel-build', 'integrate', 'verify', 'finish')


def number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise h.KitError(name + ' must be a finite ' + ('positive' if positive else 'nonnegative') + ' number')


def graph(plan):
    """List order serializes a session. Distinct sessions may overlap only by plan."""
    edges, last = {}, {}
    for task in plan['tasks']:
        deps = set(task['depends_on'])
        if task['session'] in last:
            deps.add(last[task['session']])
        edges[task['id']] = deps
        last[task['session']] = task['id']
    return edges


def validate(plan):
    if not isinstance(plan, dict) or plan.get('schema_version') != 1:
        raise h.KitError('Time plan needs schema_version=1')
    number(plan.get('reserve_minutes'), 'reserve_minutes')
    number(plan.get('review_after_minutes'), 'review_after_minutes', positive=True)
    tasks = c.identified(plan.get('tasks'), 'time-plan tasks')
    if not tasks or len(tasks) > 30:
        raise h.KitError('Use 1..30 bounded planning tasks')
    for tid, task in tasks.items():
        c.text_fields(task, ('title', 'session', 'basis', 'cut_if_late'), tid)
        if not h.ID_RE.fullmatch(task['session']) or task.get('phase') not in PHASES:
            raise h.KitError('Time-plan task needs a session ID and known phase')
        if task.get('status') not in ('pending', 'running', 'done', 'deferred') or task.get('priority') not in ('required', 'optional'):
            raise h.KitError('Invalid planning status or priority')
        values = task.get('remaining_minutes')
        if not isinstance(values, list) or len(values) != 2:
            raise h.KitError('remaining_minutes must be [low, high]')
        for value in values:
            number(value, 'remaining_minutes')
        if values[0] > values[1]:
            raise h.KitError('Remaining low estimate exceeds high estimate')
        if task['status'] in ('done', 'deferred') and values != [0, 0]:
            raise h.KitError('Done/deferred work has zero remaining estimate')
        if task['status'] == 'deferred' and task['priority'] != 'optional':
            raise h.KitError('Do not defer a required behavior to make the plan fit')
        c.refs(task.get('depends_on'), tasks, 'time-plan dependencies', empty=True)
        if task['status'] not in ('done', 'deferred') and any(tasks[d]['status'] == 'deferred' for d in task['depends_on']):
            raise h.KitError('Active work depends on deferred work; revise its real dependencies')
    edges = graph(plan)
    visited, visiting = set(), set()
    def visit(tid):
        if tid in visiting:
            raise h.KitError('Time-plan dependency/session order cycle')
        if tid in visited:
            return
        visiting.add(tid)
        for dep in edges[tid]:
            visit(dep)
        visiting.remove(tid); visited.add(tid)
    for tid in tasks:
        visit(tid)
    return plan


def context(state):
    """Planning review triggers, separate from acceptance evidence."""
    value = {k: state.get(k) for k in ('phase', 'model_revision', 'engine', 'questions', 'paused')}
    return h.digest_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def summary(state, now):
    saved = state.get('time_plan')
    if not saved:
        return None
    plan = saved['plan']
    tasks, edges = {t['id']: t for t in plan['tasks']}, graph(plan)
    def length(index):
        memo = {}
        def end(tid):
            if tid not in memo:
                memo[tid] = tasks[tid]['remaining_minutes'][index] + max((end(d) for d in edges[tid]), default=0)
            return memo[tid]
        return max((end(tid) for tid in tasks), default=0)
    low, high = length(0), length(1)
    left = (datetime.fromisoformat(state['deadline']) - now).total_seconds() / 60
    age = max(0, (now - datetime.fromisoformat(saved['at'])).total_seconds() / 60)
    reserve = plan['reserve_minutes']
    final_work = sum(t['remaining_minutes'][1] for t in tasks.values() if t['phase'] in ('verify', 'finish'))
    review = []
    if saved['context'] != context(state):
        review.append('단계·질답·모델 변경')
    if age >= plan['review_after_minutes']:
        review.append('정기 재산정 시점')
    if low + reserve > left:
        review.append('낙관 추정도 예산 초과')
    elif high + reserve > left:
        review.append('보수적 추정에서 예산 초과')
    waiting = [q['id'] for q in c.blockers(state)]
    return dict(low=low, high=high, remaining=left, reserve=reserve,
                slack=left-high-reserve, review=review, age=age, waiting=waiting,
                freeze_optional=left <= reserve+final_work)


def render(state, now):
    estimate = summary(state, now)
    if estimate is None:
        return ['시간 계획: 미작성 · 자료를 훑은 뒤 작업별 남은 시간 범위·예비 시간을 기록합니다.', '']
    saved = state['time_plan']
    lines = [f"시간 계획 r{saved['revision']}: 남은 작업 추정 {estimate['low']:.1f}–{estimate['high']:.1f}분 + 예비 {estimate['reserve']:.1f}분",
             f"보수적 추정 후 여유: {estimate['slack']:.1f}분 / 재산정: {', '.join(estimate['review']) or '현재 기록 유지'}",
             '의존관계와 같은 담당의 순서를 반영한 추정입니다. 자동 진행률·완료 보장이 아니며 HR 대기시간은 포함하지 않습니다.']
    if estimate['waiting']:
        lines.append('조건부 추정: 미해결 결정 ' + ', '.join(estimate['waiting']) + ' · 대기시간 미상, 독립 작업만 진행')
    if estimate['freeze_optional']:
        lines.append('시간 정책: 선택 기능 중지 · 검증·인계와 예비 시간 보호')
    lines += ['', '| 작업 | 담당 | 상태 | 남은 추정(분) |', '|---|---|---|---|']
    for task in saved['plan']['tasks']:
        affected = [q['id'] for q in c.blockers(state) if '*' in q['blocks'] or task['session'] in q['blocks']]
        status = task['status'] + (' / 답변 대기 ' + ','.join(affected) if affected and task['status'] not in ('done', 'deferred') else '')
        low, high = task['remaining_minutes']
        lines.append('| ' + ' | '.join(h.md_cell(v) for v in (task['title'], task['session'], status, f'{low:g}–{high:g}')) + ' |')
    return lines + ['']
