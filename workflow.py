#!/usr/bin/env python3
"""Task-local workflow, session board and bounded process timing. No model calls."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
import uuid

try:
    import harness as h
except ModuleNotFoundError:
    import runner as h
import coordination as c
import planning
import async_questions as aq
import specification as spec

PHASES = ("intake", "modeling", "parallel-build", "integrate", "verify", "finish")
PHASE_LABELS = dict(zip(PHASES, ("자료 분석", "모델링", "구현", "통합", "검증", "마무리")))
ANSWER_SOURCES = ("user-copied-hr", "user-decision", "provided-document")
SOURCE_LABELS = {"user-copied-hr": "사용자가 전달한 담당자 답변 (직접 인증 아님)",
                 "user-decision": "사용자 결정 (담당자 확인 아님)",
                 "provided-document": "제공 문서 (외부 답변 아님)"}
ROUTES = {
    "start": ("intake", "task-intake", "문제와 데이터를 읽고 필수 조건·확인 방법을 정리합니다. 중요한 모호함만 질문합니다."),
    "inputs-reviewed": ("modeling", "solver-modeling", "명세·HR 모호함을 검토한 뒤 해결 방법을 작은 입력으로 실행합니다."),
    "hr-answer": (None, "stakeholder-bridge", "답변 원문과 해석을 분리하고 영향받는 조건을 확인합니다."),
    "requirements-changed": ("modeling", "solver-modeling", "바뀐 조건을 모델·입출력 명세·검사에 반영하고 다시 확인합니다."),
    "contract-ready": ("parallel-build", "task-build", "공유 입출력을 기준으로 파일 담당을 나누고 첫 전체 동작을 구현합니다."),
    "candidate-ready": ("integrate", "task-build", "실제 계산 결과를 저장·조회와 연결하고 발행 전 규칙을 확인합니다."),
    "integrated": ("verify", "task-verify", "정상 입력과 오류·경계·데이터 변경 상황을 검사합니다."),
    "check-failed": (None, "task-build", "실패를 재현하고 원인을 좁혀 수정한 뒤 관련 검사를 다시 실행합니다."),
    "claim-complete": ("verify", "task-verify", "현재 코드의 실제 검사 결과와 빠진 항목을 확인합니다."),
    "verified": ("finish", "task-finish", "실제 결과와 문서를 맞추고 필요한 산출물을 인계합니다."),
}
WORKER_STATES = ("running", "waiting", "blocked", "done")
ENGINES = ("ortools-cp-sat", "ortools-routing", "timefold", "baseline")
ALLOWED = {
    "inputs-reviewed": set(PHASES), "requirements-changed": set(PHASES),
    "contract-ready": {"modeling"}, "candidate-ready": {"parallel-build"},
    "integrated": {"integrate"}, "verified": {"verify", "finish"},
    "check-failed": {"parallel-build", "integrate", "verify", "finish"},
    "claim-complete": {"parallel-build", "integrate", "verify", "finish"},
}


def utc():
    return datetime.now(timezone.utc)


def stamp(value=None):
    return (value or utc()).isoformat(timespec="seconds")


def path(root, name):
    return h.safe_path(root, ".harness/work/" + name)


def read_state(root):
    data = h.load_json(path(root, "workflow.json"))
    if data.get("schema_version") != 2 or data.get("phase") not in PHASES:
        raise h.KitError("Unsupported workflow state; use a fresh v3 workspace (do not overwrite old evidence)")
    return data


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise h.KitError(name + " must be finite and positive")


@contextmanager
def locked(root):
    """Short serialized mutations; a busy lock fails visibly, never breaks a live lock."""
    lock = path(root, "workflow.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "host": platform.node(), "created_at": stamp()}, f)
    except FileExistsError as exc:
        raise h.KitError("Workflow writer busy. Retry; inspect a persistent lock before removing it.") from exc
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def append_event(root, kind, data):
    with path(root, "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": stamp(), "kind": kind, **data}, ensure_ascii=False) + "\n")


def effective_worker(root, worker):
    """The immutable completed run wins over a delayed final board update."""
    worker = dict(worker)
    if worker.get("status") == "running" and worker.get("run_id"):
        record = path(root, f"runs/{worker['run_id']}.json")
        if record.exists():
            run = h.load_json(record)
            if run.get("finished_at"):
                worker.update(status="waiting" if run["exit_code"] == 0 else "blocked",
                              updated_at=run["finished_at"],
                              next_action="Review completed run: " + run["log"])
    return worker


def render(root):
    state = read_state(root)
    now = utc()
    session = h.load_json(path(root, "state.json"))
    closed = session.get("phase") == "closed"
    clock_end = datetime.fromisoformat(session["closed_at"]) if closed else now
    remaining = (datetime.fromisoformat(state["deadline"]) - clock_end).total_seconds()
    elapsed = (clock_end - datetime.fromisoformat(state["started_at"])).total_seconds()
    fixed = fixed_time(state)
    time_label = '설정 마감까지' if fixed else '유연한 목표까지'
    lines = ["# 작업 현황", "", f"갱신: {stamp(now)}", "",
             f"단계: {'종료' if closed else PHASE_LABELS[state['phase']]} ({PHASES.index(state['phase'])+1}/{len(PHASES)}) / 솔버: {state.get('engine') or '미선택'}",
             f"진행: {'종료' if closed else '관련 작업·단계 전환 대기 / 독립 작업 가능' if state.get('paused') else '진행 가능'} / 모델 변경 번호: {state.get('model_revision',0)}",
             f"담당자 DM: {contact_label(state)}",
             f"전체 경과: {max(0, elapsed)/60:.1f}분 / {'종료 시 남은 예산' if closed else time_label}: {remaining/60:.1f}분",
             f"명세·HR 검토: {'기록 있음 · 실행 전 최신성 재확인' if state.get('model_review') else '미기록 · 업무 모델 실행 전 필수'}",
             f"다음 행동: {state['next_action']}", f"읽을 지침: {state['skill']}", "",
             "시간은 설정 예산과 실측값이다. 최적해 도달 ETA나 완료율을 의미하지 않는다.", "",
             f"시간 정책: {'종료 시각 기준 기록' if closed else '설정 마감 경과 · 실행 금지' if fixed and remaining <= 0 else '유연한 목표 경과 · 계속 가능, 계획 재산정' if not fixed and remaining <= 0 else '작업별 계획 참조' if state.get('time_plan') else '임시 기준: 검증·인계 시간 보호' if fixed and remaining <= 1800 else '작업 규모에 따라 재산정'}", '']
    lines += planning.render(state, clock_end)
    lines += [aq.inbox_status(root, state), '질문 문서: .harness/work/hr-outbox.md / 받은 원문: .harness/work/hr-inbox.md',
              '메인 흐름·디자인 인계: .harness/work/main-session.md (메인 세션이 작성; 갱신 시각 확인)',
              "", "| 질문 | 상태 | 발견 단계 | 중단 작업 | 영향 |", "|---|---|---|---|---|"]
    for q in state.get('questions', {}).values():
        lines.append('| ' + ' | '.join(h.md_cell(x) for x in (q['id'], q['status'], q['phase'], ', '.join(q['blocks']), q['impact'])) + ' |')
    lines += ["", "| 세션 | 상태 | 작업 | 경과 | 갱신 | 다음 / 장애물 |",
             "|---|---|---|---|---|---|"]
    for file in sorted(path(root, "workers").glob("*.json")):
        w = effective_worker(root, h.load_json(file))
        age = (now - datetime.fromisoformat(w["updated_at"])).total_seconds()
        status = w["status"]
        if session_blockers(state, w['id']) and status != 'done':
            status = 'blocked (답변 필요)'
        if status == "running" and age > 120:
            status = "stale (확인 필요)"
        end = datetime.fromisoformat(w.get("finished_at") or stamp(now))
        duration = max(0, (end - datetime.fromisoformat(w["started_at"])).total_seconds())
        cells = [w["id"], status, w["task"], f"{duration:.0f}s", w["updated_at"], w["next_action"]]
        lines.append("| " + " | ".join(h.md_cell(x) for x in cells) + " |")
    lines += ["", "| 최근 실행 | 엔진 | 실제 경과 | 외부 제한 | 종료 | 로그 |", "|---|---|---|---|---|---|"]
    runs = []
    for f in path(root, "runs").glob("*.json"):
        runs.append(h.load_json(f))
    for run in sorted(runs, key=lambda x: x["started_at"])[-8:]:
        end = datetime.fromisoformat(run.get("finished_at") or stamp(now))
        duration = run.get("duration_seconds", max(0, (end-datetime.fromisoformat(run["started_at"])).total_seconds()))
        cells = [run["id"], run["engine"], f"{duration:.2f}s" if duration is not None else 'unknown', f"{run['limit_seconds']}s",
                 run["reason"], run["log"]]
        lines.append("| " + " | ".join(h.md_cell(x) for x in cells) + " |")
    lines += ["", "프로세스 종료 성공은 업무 규칙 검증 성공이 아니다. 실제 증거는 runner.py audit로 확인한다.",
              "수동 세션은 작업 시작·변경·종료 시 갱신한다. run으로 감싼 명령은 실행 중 자동 갱신한다.", ""]
    dest = path(root, "STATUS.md")
    if dest.exists() and dest.is_symlink():
        raise h.KitError("Refusing symlink status")
    temp = dest.with_name("STATUS.md.tmp-" + uuid.uuid4().hex)
    try:
        temp.write_text("\n".join(lines), encoding="utf-8")
        os.replace(temp, dest)
    finally:
        temp.unlink(missing_ok=True)
    return "\n".join(lines)


def start(root, minutes=None, time_mode=None):
    if time_mode == 'fixed' and minutes is None:
        raise h.KitError('Supply the actual --minutes for fixed time; omit time mode for a flexible target')
    mode = time_mode or ('flexible' if minutes is None else 'fixed')
    if mode not in ('fixed', 'flexible'):
        raise h.KitError('Time mode must be fixed or flexible')
    minutes = 180 if minutes is None else minutes
    positive(minutes, "minutes")
    h.init(root)
    h.require_working(root)
    with locked(root):
        if path(root, "workflow.json").exists():
            print(render(root))
            return 0
        templates = Path(__file__).resolve().parent / "templates"
        for name in ("main-session.md", "model-spec.md", "spec-review.json", "architecture.md", "questions.md", "AI_collaboration.md", "limits.md", "contract.json", "intake.json", "GLOSSARY.md"):
            dest = path(root, name)
            if not dest.exists():
                content = (templates / name).read_bytes()
                with dest.open("xb") as f:
                    f.write(content)
        now = utc()
        phase, skill, action = ROUTES["start"]
        h.write_json(path(root, "workflow.json"), {"schema_version": 2, "phase": phase,
                     "skill": skill, "next_action": action, "started_at": stamp(now),
                     "deadline": stamp(now + timedelta(minutes=minutes)), "updated_at": stamp(now),
                     "time_policy": {"mode": mode, "reason": "Explicit starting budget" if mode == 'fixed' else "Provisional planning target; revise after intake"},
                     "engine": None, "contract_revision": None, "contract_sha256": None,
                     "intake_review": None, "model_revision": 0, "questions": {}, "paused": None,
                     "contact": {"mode": "unspecified", "note": "필요할 때만 확인"}}, exclusive=True)
        append_event(root, "start", {"budget_minutes": minutes, "time_mode": mode})
        render_questions(root, read_state(root))
        print(render(root))
    return 0


def contract_check(root):
    contract = h.load_json(path(root, "contract.json"))
    for name in ("revision", "input", "output", "failure_behavior", "owner"):
        h.nonempty_string(contract.get(name), "contract." + name)
    if not contract.get("requirement_ids") or not isinstance(contract["requirement_ids"], list):
        raise h.KitError("Contract needs requirement_ids")
    task = h.validate_task(root)
    ids = {r["id"] for r in task["requirements"]}
    c.refs(contract['requirement_ids'], ids, 'contract requirements')
    return contract["revision"]


def event(root, name, note):
    h.require_working(root)
    h.nonempty_string(note, "event note")
    with locked(root):
        state = read_state(root)
        if name not in ALLOWED or state['phase'] not in ALLOWED[name]:
            raise h.KitError('Invalid phase transition; use start, question or resume as documented')
        if state.get('paused') or c.blockers(state):
            raise h.KitError('HR-dependent progression paused; reconcile questions and resume. Independent tasks may continue.')
        if name == 'inputs-reviewed':
            state['intake_review'] = c.intake_check(root, state)
            state['contract_revision'] = None
            state['contract_sha256'] = None
            state['model_review'] = None
        if name == "contract-ready":
            c.current_intake(root, state)
            if not state.get("engine"):
                raise h.KitError("Select the engine (or baseline) with a reason first")
            spec.current(root, state)
            state["contract_revision"] = contract_check(root)
            state['contract_sha256'] = c.contract_signature(root)
        if name in ('candidate-ready', 'integrated', 'claim-complete', 'verified'):
            c.current_intake(root, state)
            c.current_contract(root, state)
            spec.current(root, state)
        if name == "verified" and not h.audit_result(root)["local_checks_satisfied"]:
            raise h.KitError("Current configured checks are not satisfied; inspect runner.py audit")
        if name == "requirements-changed":
            state["contract_revision"] = None
            state['contract_sha256'] = None
            state['intake_review'] = None
            state['model_revision'] += 1
            state['model_review'] = None
        phase, skill, action = ROUTES[name]
        if name == 'check-failed' and state['phase'] == 'finish':
            phase = 'verify'
        state.update(phase=phase or state["phase"], skill=skill, next_action=action, updated_at=stamp())
        h.write_json(path(root, "workflow.json"), state)
        append_event(root, name, {"note": note, "phase": state["phase"]})
        print(render(root))
    return 0


def select(root, engine, reason, alternative, evidence):
    h.require_working(root)
    for value in (reason, alternative, evidence):
        h.nonempty_string(value, "selection rationale")
    with locked(root):
        state = read_state(root)
        if state['phase'] != 'modeling' or state.get('paused'):
            raise h.KitError('Select an engine after intake review, in unpaused modeling')
        c.current_intake(root, state)
        state.update(engine=engine, phase="modeling", skill="solver-modeling",
                     next_action="명세·HR 검토를 기록한 뒤 작은 입력을 실행하고 공유 입출력을 확정합니다.",
                     updated_at=stamp(), contract_revision=None, contract_sha256=None, model_review=None)
        h.write_json(path(root, "workflow.json"), state)
        append_event(root, "solver-selected", {"engine": engine, "reason": reason, "alternative": alternative, "evidence": evidence})
        with path(root, "decisions.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## 솔버 선택 · {stamp()}\n\n- 선택: {engine}\n- 이유: {reason}\n- 대안과 비용: {alternative}\n- 확인 근거 / 미확인: {evidence}\n")
        print(render(root))
    return 0


def worker(root, worker_id, status, task, files, next_action, *, run_id=None):
    h.require_working(root)
    if not h.ID_RE.fullmatch(worker_id):
        raise h.KitError("Invalid session ID")
    for item in files or []:
        h.safe_path(root, item)
    h.nonempty_string(task, "task")
    with locked(root):
        state = read_state(root)
        if status == 'running':
            ensure_time(state)
            if session_blockers(state, worker_id):
                raise h.KitError('Session blocked by unresolved decisions: ' + ', '.join(session_blockers(state, worker_id)))
        target = path(root, f"workers/{worker_id}.json")
        old = effective_worker(root, h.load_json(target)) if target.exists() else {}
        if old.get("run_id") and old.get("status") == "running" and old["run_id"] != run_id:
            raise h.KitError("Session is owned by an active timed run")
        files = old.get("files", []) if files is None else files
        files = [Path(x).as_posix().rstrip("/") for x in files]
        for f in path(root, "workers").glob("*.json"):
            other = effective_worker(root, h.load_json(f))
            if other["id"] == worker_id or other["status"] == "done" or status == "done":
                continue
            for a in files:
                for b in other["files"]:
                    if a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                        raise h.KitError(f"File ownership conflict with {other['id']}: {a}")
        now = stamp()
        data = {"id": worker_id, "status": status, "task": task, "files": files,
                "started_at": old.get("started_at", now) if old.get("status") != "done" and old.get("task") == task and old.get("run_id") == run_id else now,
                "updated_at": now, "next_action": next_action, "run_id": run_id,
                "contract_revision": state.get('contract_revision')}
        if status == "done":
            data["finished_at"] = now
        h.write_json(target, data)
        render(root)
    return data


def fixed_time(state):
    return state.get('time_policy', {}).get('mode', 'fixed') == 'fixed'


def ensure_time(state):
    if fixed_time(state) and utc() >= datetime.fromisoformat(state['deadline']):
        raise h.KitError('Configured work deadline passed. Do not run more work; check actual phase/rules with the user.')


def schedule(root, remaining_minutes, mode, reason, source_file=None):
    """Adjust a planning target; changed actual deadlines need recorded evidence."""
    h.require_working(root)
    positive(remaining_minutes, 'remaining minutes')
    h.nonempty_string(reason, 'schedule reason')
    if mode not in ('fixed', 'flexible'):
        raise h.KitError('Time mode must be fixed or flexible')
    with locked(root):
        state = read_state(root)
        if (fixed_time(state) or mode == 'fixed') and not source_file:
            raise h.KitError('Changing an actual deadline needs --source-file with the actual instruction; use plan for allocation only')
        evidence = None
        if source_file:
            file = h.safe_path(root, source_file)
            h.nonempty_string(file.read_text(encoding='utf-8'), 'time instruction')
            evidence = {'path': source_file, 'sha256': h.digest_file(file)}
        before = {'deadline': state['deadline'], 'time_policy': state.get('time_policy')}
        state['deadline'] = stamp(utc() + timedelta(minutes=remaining_minutes))
        state['time_policy'] = {'mode': mode, 'reason': reason, 'source': evidence}
        state['updated_at'] = stamp()
        h.write_json(path(root, 'workflow.json'), state)
        append_event(root, 'schedule-revised', {'before': before, 'deadline': state['deadline'],
                     'remaining_minutes': remaining_minutes, 'time_policy': state['time_policy']})
        print(render(root))
    return 0


def review_model(root, note):
    h.require_working(root)
    h.nonempty_string(note, 'model/HR review note')
    with locked(root):
        state = read_state(root)
        state['model_review'] = {'at': stamp(), 'note': note, 'signature': spec.signature(root, state)}
        state['updated_at'] = stamp()
        h.write_json(path(root, 'workflow.json'), state)
        append_event(root, 'model-reviewed', state['model_review'])
        print(render(root))
    return 0


def session_blockers(state, session):
    return [q['id'] for q in c.blockers(state) if '*' in q['blocks'] or session in q['blocks']]


def contact_label(state):
    return {"none": "없음 · 문서 근거와 사용자 결정으로 진행",
            "manual": "있음 · 사용자가 직접 전달",
            "unspecified": "미설정 · 필요할 때만 확인"}.get(state.get('contact', {}).get('mode', 'unspecified'), '미설정')


def set_plan(root, file, reason):
    h.require_working(root)
    h.nonempty_string(reason, 'planning reason')
    proposed = planning.validate(h.load_json(h.safe_path(root, file)))
    with locked(root):
        state = read_state(root)
        revision = state.get('time_plan', {}).get('revision', 0) + 1
        state['time_plan'] = {'revision': revision, 'at': stamp(), 'reason': reason,
                              'context': planning.context(state), 'plan': proposed}
        state['updated_at'] = stamp()
        h.write_json(path(root, 'workflow.json'), state)
        append_event(root, 'time-plan', {'revision': revision, 'reason': reason, 'plan': proposed})
        print(render(root))
    return 0


def import_answers(root, file, source):
    h.require_working(root)
    if source not in ANSWER_SOURCES:
        raise h.KitError('Unknown answer source')
    raw = h.safe_path(root, file).read_bytes()
    with locked(root):
        state = read_state(root)
        staged = aq.stage_answers(state, raw.decode('utf-8-sig'))
        for qid, text in staged:
            q = state['questions'][qid]
            q['answers'].append({'text': text, 'path': file, 'sha256': h.digest_bytes(raw),
                                 'actor': source, 'recorded_at': stamp()})
            q['status'] = 'answered'
            q.pop('assessment', None)
        if staged:
            state['updated_at'] = stamp()
            h.write_json(path(root, 'workflow.json'), state)
            append_event(root, 'answers-imported', {'ids': [qid for qid, _ in staged], 'source': source})
        render_questions(root, state)
        print(f'Imported {len(staged)} actual answer(s); no model change or automatic resume.')
        print(render(root))
    return 0


def question_next(state):
    if state.get('contact', {}).get('mode') == 'none':
        return 'DM 요청 없이 문서 근거를 확인합니다. 결과를 바꾸는 중요한 미결정만 사용자에게 묻고 반영 후 재개합니다.'
    return '질문 문서를 사용자가 수동 전달 → 답변함에 실제 원문 추가 → 명세·검사 반영 → 재개. 독립 작업은 계속합니다.'


def contact(root, mode, note):
    """Remember contact availability; never erase or resolve existing questions."""
    h.require_working(root)
    if mode not in ('manual', 'none'):
        raise h.KitError('Contact mode must be manual or none')
    h.nonempty_string(note, 'contact note')
    with locked(root):
        state = read_state(root)
        state['contact'] = {'mode': mode, 'note': note, 'updated_at': stamp()}
        if state.get('paused'):
            state['next_action'] = question_next(state)
        state['updated_at'] = stamp()
        h.write_json(path(root, 'workflow.json'), state)
        append_event(root, 'contact-mode', {'mode': mode, 'note': note})
        render_questions(root, state)
        print(render(root))
    return 0


def render_questions(root, state):
    lines = ['# 질문과 결정', '', '자동 생성된 보기. 원본 상태는 workflow.json이며 원문과 해석을 구분한다.',
             '', '담당자 DM: ' + contact_label(state), '']
    for q in state['questions'].values():
        lines += [f"## {q['id']} · {q['status']}", '', q['text'], '',
                  f"- 발견 단계: {q['phase']}", f"- 영향: {q['impact']}",
                  f"- 멈추는 작업: {', '.join(q['blocks']) or '없음'}",
                  f"- 미응답 가정 / 제한: {q['assumption']}", f"- 선행 질문: {', '.join(q['requires']) or '없음'}"]
        for answer in q.get('answers', []):
            actor = answer.get('actor', 'user-copied-hr')
            lines += ['', f"### 근거 원문 · 기록시각 {answer['recorded_at']}", '',
                      f"출처: {actor} · {SOURCE_LABELS.get(actor, actor)}", '',
                      *['> ' + line for line in answer['text'].splitlines()]]
        if q.get('interpretation'):
            lines += ['', '### AI 해석 / 반영', '', q['interpretation'],
                      f"- 확인할 검사: {', '.join(q['checks'])}",
                      '- 반영 파일: ' + ', '.join(q['updates'])]
        for conflict in q.get('conflicts', []):
            lines += ['', '### 충돌 기록', '', conflict['note']]
        for assessment in q.get('assessments', []):
            lines += ['', f"### 답변 검토 · {assessment['verdict']} · 원문 {assessment['answer_count']}개 시점", '', assessment['meaning']]
            if assessment.get('example'):
                lines += ['- 확인 사례: ' + assessment['example'], '- 예상 결과: ' + assessment['expected']]
            if assessment.get('remaining'):
                lines += ['- 남은 모호함: ' + assessment['remaining'], '- 추가 질문: ' + assessment['followup']]
        lines.append('')
    path(root, 'questions.md').write_text('\n'.join(lines), encoding='utf-8')
    aq.render(root, state)


def question(root, args):
    h.require_working(root)
    if not h.ID_RE.fullmatch(args.id):
        raise h.KitError('Invalid question ID')
    with locked(root):
        state = read_state(root)
        questions = state['questions']
        if args.action == 'ask':
            if args.id in questions:
                raise h.KitError('Question ID already exists; preserve it and use a new follow-up ID')
            for value in (args.text, args.impact, args.assumption):
                h.nonempty_string(value, 'question detail')
            if any(x not in questions or questions[x]['status'] != 'resolved' for x in args.requires):
                raise h.KitError('Ask the ready frontier only: prerequisite questions must be resolved')
            blocking = not args.nonblocking
            blocks = args.blocks or (['*'] if blocking else [])
            if any(x != '*' and not h.ID_RE.fullmatch(x) for x in blocks):
                raise h.KitError('blocks must be session IDs or *')
            if not blocking and blocks:
                raise h.KitError('A nonblocking question cannot block sessions')
            q = {'id': args.id, 'text': args.text, 'impact': args.impact, 'assumption': args.assumption,
                 'kind': getattr(args, 'kind', 'business-rule'),
                 'blocking': blocking, 'blocks': blocks, 'requires': args.requires,
                 'status': 'pending', 'phase': state['phase'], 'created_at': stamp(), 'answers': []}
            questions[args.id] = q
            if blocking and not state.get('paused'):
                state['paused'] = {'phase': state['phase'], 'skill': state['skill'], 'at': stamp()}
        else:
            if args.id not in questions:
                raise h.KitError('Unknown question ID')
            q = questions[args.id]
            if args.action == 'sent':
                h.nonempty_string(args.note, 'user-reported delivery note')
                if state.get('contact', {}).get('mode') != 'manual' or q['status'] not in ('pending', 'conflict', 'needs-clarification'):
                    raise h.KitError('Record sent only for a pending manual-DM question after the user reports delivery')
                q['delivery'] = {'at': stamp(), 'note': args.note, 'actor': 'user-reported'}
            elif args.action == 'answer':
                if q['status'] not in ('pending', 'conflict', 'needs-clarification'):
                    raise h.KitError('Answer already recorded; mark conflict or create a follow-up')
                answerfile = h.safe_path(root, args.file)
                text = answerfile.read_text(encoding='utf-8')
                h.nonempty_string(text, 'answer')
                actor = getattr(args, 'source', None) or ('user-decision' if state.get('contact', {}).get('mode') == 'none' else 'user-copied-hr')
                if actor not in ANSWER_SOURCES:
                    raise h.KitError('Unknown answer source')
                q['answers'].append({'text': text, 'path': args.file, 'sha256': h.digest_file(answerfile),
                                     'actor': actor, 'recorded_at': stamp()})
                q['status'] = 'answered'
                q.pop('assessment', None)
            elif args.action == 'assess':
                spec.assess(q, args, stamp())
            elif args.action == 'conflict':
                h.nonempty_string(args.note, 'conflict note')
                q.setdefault('conflicts', []).append({'at': stamp(), 'note': args.note})
                q['status'] = 'conflict'
                q.pop('assessment', None)
                if q['blocking'] and not state.get('paused'):
                    state['paused'] = {'phase': state['phase'], 'skill': state['skill'], 'at': stamp()}
            elif args.action == 'resolve':
                if q['status'] != 'answered':
                    raise h.KitError('Record an actual stakeholder reply, user decision or supplied document before resolution')
                if not spec.answer_ready(q):
                    raise h.KitError('Assess answer clarity with a concrete example and expected result before resolution')
                h.nonempty_string(args.interpretation, 'interpretation')
                task = h.validate_task(root)
                c.refs(args.checks, {x['id'] for x in task['checks']+task['manual_checks']}, 'resolution checks')
                if not args.updates:
                    raise h.KitError('Record at least one actual reviewed/updated local file')
                updates = {p: h.digest_file(h.safe_path(root, p)) for p in args.updates}
                q.update(status='resolved', interpretation=args.interpretation, updates=updates,
                         checks=args.checks, material_change=args.changed, resolved_at=stamp())
                if args.changed:
                    state.update(phase='modeling', intake_review=None, contract_revision=None, contract_sha256=None,
                                 model_revision=state['model_revision']+1, model_review=None)
                    if state.get('paused'):
                        state['paused']['return_to_modeling'] = True
        if state.get('paused'):
            state.update(skill='stakeholder-bridge', next_action=question_next(state))
        state['updated_at'] = stamp()
        h.write_json(path(root, 'workflow.json'), state)
        append_event(root, 'question-' + args.action, {'id': args.id, 'status': q['status']})
        render_questions(root, state)
        print(render(root))
    return 0


def resume(root, note):
    h.require_working(root)
    h.nonempty_string(note, 'resume note')
    with locked(root):
        state = read_state(root)
        if c.blockers(state):
            raise h.KitError('Unresolved blocking questions: ' + ', '.join(q['id'] for q in c.blockers(state)))
        paused = state.get('paused')
        if paused:
            phase = 'modeling' if paused.get('return_to_modeling') else paused['phase']
            skill = 'solver-modeling' if paused.get('return_to_modeling') else paused['skill']
            state.update(phase=phase, skill=skill, paused=None, updated_at=stamp(),
                         next_action='조건·입출력 명세가 바뀌었는지 확인하고 관련 검사를 다시 실행한 뒤 기존 단계에서 이어갑니다.')
            h.write_json(path(root, 'workflow.json'), state)
            append_event(root, 'resumed', {'note': note, 'phase': phase})
        print(render(root))
    return 0


def recover_lock(root):
    """Recover only an observed dead local PID. Never assume age implies death."""
    h.require_working(root)
    lock = path(root, 'workflow.lock')
    data = h.load_json(lock)
    if data.get('host') != platform.node() or type(data.get('pid')) is not int or data['pid'] <= 0:
        raise h.KitError('Lock owner is unknown/different host; inspect manually')
    try:
        os.kill(data['pid'], 0)
    except ProcessLookupError:
        if h.load_json(lock) != data:
            raise h.KitError('Lock changed while inspecting; retry')
        lock.unlink()
        append_event(root, 'dead-lock-recovered', data)
        return 0
    except PermissionError as exc:
        raise h.KitError('Lock process existence is uncertain') from exc
    raise h.KitError('Lock owner is still alive; do not remove it')


def recover_run(root, run_id, note):
    h.require_working(root)
    h.nonempty_string(note, 'recovery note')
    if not run_id or any(x not in '0123456789Tabcdef-' for x in run_id):
        raise h.KitError('Invalid run ID')
    with locked(root):
        target = path(root, 'runs/' + run_id + '.json')
        run = h.load_json(target)
        if run.get('finished_at'):
            raise h.KitError('Run already completed; inspect the existing evidence')
        if run.get('host') != platform.node() or not run.get('child_pid'):
            raise h.KitError('Cannot prove local process ownership; inspect processes manually')
        for pid in (run['supervisor_pid'], run['child_pid']):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            except PermissionError as exc:
                raise h.KitError('Process status uncertain') from exc
            raise h.KitError('Recorded process is still alive; recovery must not kill or replace it')
        logfile = h.safe_path(root, run['log'])
        run.update(finished_at=stamp(), reason='abandoned', exit_code=None, process_exit_code=None,
                   duration_seconds=None, workspace_changed=True, recovery_note=note,
                   log_sha256=h.digest_file(logfile) if logfile.exists() else None)
        h.write_json(target, run)
        append_event(root, 'abandoned-run', {'id': run_id, 'note': note})
    print('Marked abandoned with unknown exit/time; this is not a successful timing sample.')
    return 0


def extra_snapshot(root, inputs):
    declared = {name: h.digest_file(h.safe_path(root, name)) for name in inputs}
    kit_sources = {}
    for folder in ("examples", "templates"):
        base = h.safe_path(root, ".harness/" + folder)
        if base.exists():
            for f in sorted(base.rglob("*")):
                if f.is_file() and not any(x in f.parts for x in ("target", "__pycache__", ".venv")) and f.name != "classpath.txt":
                    h.safe_path(root, f.relative_to(root).as_posix())
                    kit_sources[f.relative_to(root).as_posix()] = h.digest_file(f)
    return {"declared_inputs": declared, "kit_sources": kit_sources}


def timed_run(root, args):
    h.require_working(root)
    state = read_state(root)
    ensure_time(state)
    purpose = getattr(args, 'purpose', None) or ('utility' if args.engine == 'baseline' else 'solve')
    if purpose not in ('solve', 'utility') or (args.engine != 'baseline' and purpose != 'solve'):
        raise h.KitError('Solver engines must use purpose solve; utility is only for independent environment/build work')
    if purpose == 'solve':
        if args.engine != state.get('engine'):
            raise h.KitError('Run engine must match the reviewed model')
        spec.current(root, state)
    positive(args.limit, "limit")
    if fixed_time(state) and args.limit > (datetime.fromisoformat(state['deadline']) - utc()).total_seconds():
        raise h.KitError('Outer run limit exceeds remaining work budget; reduce it')
    if not args.argv:
        raise h.KitError("Provide a command after --")
    argv = args.argv[1:] if args.argv[0] == "--" else args.argv
    if not argv:
        raise h.KitError("Empty command")
    cwd = h.safe_path(root, args.cwd, allow_dot=True)
    extra_before = extra_snapshot(root, args.input)
    inputs = extra_before["declared_inputs"]
    # Fingerprint includes declared inputs, command, limit, machine and current task sources.
    source = h.snapshot(root)
    fingerprint = h.digest_bytes(json.dumps({"argv": argv, "cwd": str(cwd.relative_to(root)), "engine": args.engine, "purpose": purpose, "limit": args.limit,
        "inputs": inputs, "sources": source, "kit_sources": extra_before["kit_sources"],
        "machine": platform.platform(), "cpu_count": os.cpu_count(), "python": sys.version}, sort_keys=True).encode())
    run_id = utc().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run = {"id": run_id, "session": args.session, "engine": args.engine, "argv": argv, "cwd": args.cwd,
           "label": args.label, "purpose": purpose, "started_at": stamp(), "limit_seconds": args.limit,
           "fingerprint": fingerprint, "input_sha256": inputs, "sources": source,
           "reason": "running", "log": f".harness/work/runs/{run_id}.log",
           "host": platform.node(), "supervisor_pid": os.getpid(), "child_pid": None}
    target = path(root, f"runs/{run_id}.json")
    h.write_json(target, run, exclusive=True)
    try:
        worker(root, args.session, "running", args.label, None, "Timed command running", run_id=run_id)
        if purpose == 'solve':
            spec.current(root, read_state(root))
    except BaseException:
        run.update(reason='not_started', finished_at=stamp(), duration_seconds=0,
                   exit_code=2, process_exit_code=None, workspace_changed=False, log_sha256=None)
        h.write_json(target, run)
        raise
    logfile = h.safe_path(root, run["log"])
    start_time = time.monotonic()
    reason, code, proc = "completed", 127, None
    print(f"RUN {run_id}: outer limit={args.limit}s; log={run['log']}", flush=True)
    try:
        with logfile.open("xb") as output:
            try:
                proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                                        stderr=subprocess.STDOUT, start_new_session=os.name == "posix")
                run['child_pid'] = proc.pid
                h.write_json(target, run)
                last_heartbeat = -10.0
                while proc.poll() is None:
                    elapsed = time.monotonic() - start_time
                    live = read_state(root)
                    if session_blockers(live, args.session) or (purpose == 'solve' and c.blockers(live)):
                        reason = 'hr_blocked'
                        h.stop_process(proc)
                        break
                    if fixed_time(live) and utc() >= datetime.fromisoformat(live['deadline']):
                        reason = 'deadline'
                        h.stop_process(proc)
                        break
                    if elapsed >= args.limit:
                        reason = "timeout"
                        h.stop_process(proc)
                        break
                    if logfile.stat().st_size > h.MAX_LOG_BYTES:
                        reason = "output_limit"
                        h.stop_process(proc)
                        break
                    if elapsed - last_heartbeat >= 2:
                        print(f"{args.session}: elapsed={elapsed:.1f}s; budget_left={max(0,args.limit-elapsed):.1f}s (not ETA)", flush=True)
                        try:
                            worker(root, args.session, "running", args.label, None, "Timed command running", run_id=run_id)
                        except h.KitError:
                            pass  # A concurrent short writer may delay one heartbeat; no state overwrite.
                        last_heartbeat = elapsed
                    time.sleep(0.05)
                code = proc.wait()
            except OSError as exc:
                if proc is None:
                    reason, code = 'launch_error', 127
                else:
                    h.stop_process(proc)
                    reason, code = 'supervisor_error', proc.returncode
                output.write((str(exc) + "\n").encode())
    except BaseException:
        reason = "interrupted"
        if proc is not None:
            h.stop_process(proc)
            code = proc.returncode
        raise
    finally:
        if logfile.exists() and logfile.stat().st_size > h.MAX_LOG_BYTES:
            with logfile.open("r+b") as f:
                f.truncate(h.MAX_LOG_BYTES)
            reason = "output_limit"
        reported = {"timeout": 124, "output_limit": 125, "supervisor_error":125,
                    "interrupted": 130, "hr_blocked": 126, "deadline": 124}.get(reason, code if code >= 0 else 128-code)
        try:
            source_after = h.snapshot(root)
            extra_after = extra_snapshot(root, args.input)
            changed = not h.same_snapshot(source, source_after) or extra_after != extra_before
        except (h.KitError, OSError, ValueError) as exc:
            changed = True
            extra_after = None
            run["snapshot_error"] = str(exc)
        run.update(finished_at=stamp(), duration_seconds=round(time.monotonic()-start_time, 4),
                   reason=reason, process_exit_code=code, exit_code=reported,
                   log_sha256=h.digest_file(logfile) if logfile.exists() else None,
                   workspace_changed=changed, extra_after=extra_after)
        h.write_json(target, run)
        try:
            worker(root, args.session, "waiting" if reported == 0 else "blocked", args.label, None,
                   "Review result and run independent acceptance checks" if reported == 0 else f"Inspect {reason}: {run['log']}", run_id=run_id)
        except h.KitError as exc:
            print(f"Status refresh pending: {exc}", file=sys.stderr)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return reported


def history(root):
    groups = {}
    for file in path(root, "runs").glob("*.json"):
        run = h.load_json(file)
        if run.get("reason") == "completed" and run.get("exit_code") == 0 and not run.get("workspace_changed"):
            logfile = h.safe_path(root, run["log"])
            if logfile.is_file() and h.digest_file(logfile) == run.get("log_sha256"):
                groups.setdefault(run["fingerprint"], []).append(run)
    for key, values in groups.items():
        times = [x["duration_seconds"] for x in values]
        print(json.dumps({"fingerprint": key, "engine": values[0]["engine"], "sample_count": len(times),
            "observed_seconds": {"min": min(times), "median": statistics.median(times), "max": max(times)},
            "meaning": "Historical process durations for matching recorded settings; not solver quality, a statistical interval, or future ETA."}, ensure_ascii=False))
    if not groups:
        print("No completed, unchanged, intact timing samples yet; runtime estimate is unknown.")
    return 0


def doctor():
    for cmd, argv in (("python", [sys.executable, "--version"]), ("java", ["java", "-version"]),
                      ("javac", ["javac", "-version"]), ("mvn", ["mvn", "-version"])):
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=8)
            print(cmd + ": " + (result.stdout or result.stderr).splitlines()[0][:250])
        except (OSError, subprocess.TimeoutExpired, IndexError):
            print(cmd + ": unavailable")
    try:
        from importlib.metadata import version
        print("ortools: " + version("ortools"))
    except Exception:
        print("ortools: not installed in this Python")
    print("Timefold 2.x requires JDK 21+. Runtime presence is not proof that a solver model works.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", default=".")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start"); s.add_argument("--minutes", type=float)
    s.add_argument('--time-mode', choices=('fixed', 'flexible'))
    tm = sub.add_parser('schedule'); tm.add_argument('--remaining-minutes', type=float, required=True)
    tm.add_argument('--mode', choices=('fixed', 'flexible'), required=True)
    tm.add_argument('--reason', required=True); tm.add_argument('--source-file')
    mr = sub.add_parser('review-model'); mr.add_argument('--note', required=True)
    e = sub.add_parser("event"); e.add_argument("name", choices=ALLOWED); e.add_argument("--note", required=True)
    c = sub.add_parser("select"); c.add_argument("engine", choices=ENGINES)
    for name in ("reason", "alternative", "evidence"): c.add_argument("--"+name, required=True)
    w = sub.add_parser("worker"); w.add_argument("id"); w.add_argument("--status", choices=WORKER_STATES, required=True)
    w.add_argument("--task", required=True); w.add_argument("--files", nargs="*", default=None); w.add_argument("--next", default="")
    r = sub.add_parser("run"); r.add_argument("--session", required=True); r.add_argument("--engine", choices=ENGINES, required=True)
    r.add_argument("--label", required=True); r.add_argument("--limit", type=float, required=True); r.add_argument("--cwd", default=".")
    r.add_argument("--input", action="append", default=[]); r.add_argument("argv", nargs=argparse.REMAINDER)
    r.add_argument('--purpose', choices=('solve', 'utility'))
    v = sub.add_parser("status"); v.add_argument("--watch", action="store_true")
    sub.add_parser("history"); sub.add_parser("doctor")
    sub.add_parser('recover-lock')
    rr = sub.add_parser('recover-run'); rr.add_argument('id'); rr.add_argument('--note', required=True)
    rs = sub.add_parser('resume'); rs.add_argument('--note', required=True)
    ct = sub.add_parser('contact'); ct.add_argument('--mode', choices=('manual', 'none'), required=True); ct.add_argument('--note', required=True)
    pl = sub.add_parser('plan'); pl.add_argument('--file', required=True); pl.add_argument('--reason', required=True)
    q = sub.add_parser('question'); qa = q.add_subparsers(dest='action', required=True)
    ask = qa.add_parser('ask'); ask.add_argument('id')
    for name in ('text', 'impact', 'assumption'): ask.add_argument('--'+name, required=True)
    ask.add_argument('--blocks', nargs='+'); ask.add_argument('--requires', nargs='*', default=[])
    ask.add_argument('--nonblocking', action='store_true')
    ask.add_argument('--kind', choices=('business-rule', 'implementation'), default='business-rule')
    ans = qa.add_parser('answer'); ans.add_argument('id'); ans.add_argument('--file', required=True)
    ans.add_argument('--source', choices=ANSWER_SOURCES)
    ass = qa.add_parser('assess'); ass.add_argument('id')
    ass.add_argument('--verdict', choices=('clear', 'partial', 'ambiguous', 'conflicting', 'delegated'), required=True)
    ass.add_argument('--meaning', required=True)
    for name in ('example', 'expected', 'remaining', 'followup'): ass.add_argument('--'+name)
    sent = qa.add_parser('sent'); sent.add_argument('id'); sent.add_argument('--note', required=True)
    imp = qa.add_parser('import'); imp.add_argument('--file', default='.harness/work/hr-inbox.md')
    imp.add_argument('--source', choices=ANSWER_SOURCES, required=True)
    res = qa.add_parser('resolve'); res.add_argument('id'); res.add_argument('--interpretation', required=True)
    change = res.add_mutually_exclusive_group(required=True)
    change.add_argument('--changed', action='store_true'); change.add_argument('--unchanged', dest='changed', action='store_false')
    res.add_argument('--updates', nargs='+', required=True); res.add_argument('--checks', nargs='+', required=True)
    cf = qa.add_parser('conflict'); cf.add_argument('id'); cf.add_argument('--note', required=True)
    args = p.parse_args(argv)
    try:
        root = Path(args.project).absolute()
        if root.is_symlink() or not root.is_dir():
            raise h.KitError("Project must be an existing non-symlink directory")
        root = root.resolve()
        if args.command == "doctor": return doctor()
        if args.command == "start": return start(root, args.minutes, args.time_mode)
        if args.command == 'schedule': return schedule(root, args.remaining_minutes, args.mode, args.reason, args.source_file)
        if args.command == 'review-model': return review_model(root, args.note)
        if args.command == 'question':
            return import_answers(root, args.file, args.source) if args.action == 'import' else question(root, args)
        if args.command == 'contact': return contact(root, args.mode, args.note)
        if args.command == 'plan': return set_plan(root, args.file, args.reason)
        if args.command == 'resume': return resume(root, args.note)
        if args.command == 'recover-lock': return recover_lock(root)
        if args.command == 'recover-run': return recover_run(root, args.id, args.note)
        if args.command == "event": return event(root, args.name, args.note)
        if args.command == "select": return select(root, args.engine, args.reason, args.alternative, args.evidence)
        if args.command == "worker":
            worker(root, args.id, args.status, args.task, args.files, args.next)
            print(render(root)); return 0
        if args.command == "run": return timed_run(root, args)
        if args.command == "history": return history(root)
        if args.command == "status":
            while True:
                if args.watch and sys.stdout.isatty():
                    print('\033[2J\033[H', end='')
                print(render(root), flush=True)
                if not args.watch: return 0
                time.sleep(5)
    except KeyboardInterrupt:
        return 130
    except (h.KitError, OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
