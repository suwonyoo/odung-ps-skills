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

PHASES = ("intake", "modeling", "parallel-build", "integrate", "verify", "finish")
ROUTES = {
    "start": ("intake", "hackathon-intake", "Read supplied files; extract requirements; draft manual stakeholder questions."),
    "inputs-reviewed": ("modeling", "solver-modeling", "Compare solvers and write the model specification; run a small real prototype."),
    "hr-answer": (None, "stakeholder-bridge", "Record the user's verbatim answer separately from interpretation; assess affected constraints."),
    "requirements-changed": ("modeling", "solver-modeling", "Revise the model, contract and acceptance checks; revalidate affected results."),
    "contract-ready": ("parallel-build", "hackathon-build", "Assign disjoint files to core and integration sessions; keep one contract owner."),
    "candidate-ready": ("integrate", "hackathon-build", "Connect the real solver result to storage and UI; independently validate before publication."),
    "integrated": ("verify", "hackathon-verify", "Run real data, boundaries, failure paths and state-change checks."),
    "check-failed": (None, "hackathon-build", "Reproduce; isolate one cause; make a focused fix; rerun the failed and affected checks."),
    "claim-complete": ("verify", "hackathon-verify", "Read actual evidence; unrun, stale or failed checks are not completion."),
    "verified": ("finish", "hackathon-finish", "Align requested deliverables with actual behavior and prepare manual submission."),
}
WORKER_STATES = ("running", "waiting", "blocked", "done")
ENGINES = ("ortools-cp-sat", "ortools-routing", "timefold", "baseline")


def utc():
    return datetime.now(timezone.utc)


def stamp(value=None):
    return (value or utc()).isoformat(timespec="seconds")


def path(root, name):
    return h.safe_path(root, ".harness/work/" + name)


def read_state(root):
    data = h.load_json(path(root, "workflow.json"))
    if data.get("schema_version") != 1 or data.get("phase") not in PHASES:
        raise h.KitError("Unsupported workflow state")
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
            json.dump({"pid": os.getpid(), "created_at": stamp()}, f)
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
    closed = h.load_json(path(root, "state.json")).get("phase") == "closed"
    remaining = (datetime.fromisoformat(state["deadline"]) - now).total_seconds()
    elapsed = (now - datetime.fromisoformat(state["started_at"])).total_seconds()
    lines = ["# 작업 현황", "", f"갱신: {stamp(now)}", "",
             f"단계: {'closed' if closed else state['phase']} / 솔버: {state.get('engine') or '미선택'}",
             f"전체 경과: {max(0, elapsed)/60:.1f}분 / 설정 마감까지: {remaining/60:.1f}분",
             f"다음 행동: {state['next_action']}", f"읽을 지침: {state['skill']}", "",
             "시간은 설정 예산과 실측값이다. 최적해 도달 ETA나 완료율을 의미하지 않는다.", "",
             "| 세션 | 상태 | 작업 | 경과 | 갱신 | 다음 / 장애물 |",
             "|---|---|---|---|---|---|"]
    for file in sorted(path(root, "workers").glob("*.json")):
        w = effective_worker(root, h.load_json(file))
        age = (now - datetime.fromisoformat(w["updated_at"])).total_seconds()
        status = w["status"]
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
        cells = [run["id"], run["engine"], f"{duration:.2f}s", f"{run['limit_seconds']}s",
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


def start(root, minutes):
    positive(minutes, "minutes")
    h.init(root)
    h.require_working(root)
    with locked(root):
        if path(root, "workflow.json").exists():
            print(render(root))
            return 0
        templates = Path(__file__).resolve().parent / "templates"
        for name in ("model-spec.md", "architecture.md", "questions.md", "AI_collaboration.md", "limits.md", "contract.json"):
            dest = path(root, name)
            if not dest.exists():
                content = (templates / name).read_bytes()
                with dest.open("xb") as f:
                    f.write(content)
        now = utc()
        phase, skill, action = ROUTES["start"]
        h.write_json(path(root, "workflow.json"), {"schema_version": 1, "phase": phase,
                     "skill": skill, "next_action": action, "started_at": stamp(now),
                     "deadline": stamp(now + timedelta(minutes=minutes)), "updated_at": stamp(now),
                     "engine": None, "contract_revision": None}, exclusive=True)
        append_event(root, "start", {"budget_minutes": minutes})
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
    if any(r not in ids for r in contract["requirement_ids"]):
        raise h.KitError("Contract references unknown requirements")
    return contract["revision"]


def event(root, name, note):
    h.require_working(root)
    h.nonempty_string(note, "event note")
    with locked(root):
        state = read_state(root)
        if name == "contract-ready":
            if not state.get("engine"):
                raise h.KitError("Select the engine (or baseline) with a reason first")
            state["contract_revision"] = contract_check(root)
        if name == "verified" and not h.audit_result(root)["local_checks_satisfied"]:
            raise h.KitError("Current configured checks are not satisfied; inspect runner.py audit")
        if name == "requirements-changed":
            state["contract_revision"] = None
        phase, skill, action = ROUTES[name]
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
        state.update(engine=engine, phase="modeling", skill="solver-modeling",
                     next_action="Complete the chosen model specification and a timed prototype; freeze the contract.",
                     updated_at=stamp(), contract_revision=None)
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
        read_state(root)
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
                "updated_at": now, "next_action": next_action, "run_id": run_id}
        if status == "done":
            data["finished_at"] = now
        h.write_json(target, data)
        render(root)
    return data


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
    positive(args.limit, "limit")
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
    fingerprint = h.digest_bytes(json.dumps({"argv": argv, "cwd": str(cwd.relative_to(root)), "engine": args.engine, "limit": args.limit,
        "inputs": inputs, "sources": source, "kit_sources": extra_before["kit_sources"],
        "machine": platform.platform(), "cpu_count": os.cpu_count(), "python": sys.version}, sort_keys=True).encode())
    run_id = utc().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    worker(root, args.session, "running", args.label, None, "Timed command running", run_id=run_id)
    run = {"id": run_id, "session": args.session, "engine": args.engine, "argv": argv, "cwd": args.cwd,
           "label": args.label, "started_at": stamp(), "limit_seconds": args.limit,
           "fingerprint": fingerprint, "input_sha256": inputs, "sources": source,
           "reason": "running", "log": f".harness/work/runs/{run_id}.log"}
    target = path(root, f"runs/{run_id}.json")
    h.write_json(target, run, exclusive=True)
    logfile = h.safe_path(root, run["log"])
    start_time = time.monotonic()
    reason, code, proc = "completed", 127, None
    print(f"RUN {run_id}: outer limit={args.limit}s; log={run['log']}", flush=True)
    try:
        with logfile.open("xb") as output:
            try:
                proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                                        stderr=subprocess.STDOUT, start_new_session=os.name == "posix")
                last_heartbeat = -10.0
                while proc.poll() is None:
                    elapsed = time.monotonic() - start_time
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
                reason = "launch_error"
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
        reported = {"timeout": 124, "output_limit": 125, "interrupted": 130}.get(reason, code if code >= 0 else 128-code)
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
    s = sub.add_parser("start"); s.add_argument("--minutes", type=float, default=180)
    e = sub.add_parser("event"); e.add_argument("name", choices=ROUTES); e.add_argument("--note", required=True)
    c = sub.add_parser("select"); c.add_argument("engine", choices=ENGINES)
    for name in ("reason", "alternative", "evidence"): c.add_argument("--"+name, required=True)
    w = sub.add_parser("worker"); w.add_argument("id"); w.add_argument("--status", choices=WORKER_STATES, required=True)
    w.add_argument("--task", required=True); w.add_argument("--files", nargs="*", default=None); w.add_argument("--next", default="")
    r = sub.add_parser("run"); r.add_argument("--session", required=True); r.add_argument("--engine", choices=ENGINES, required=True)
    r.add_argument("--label", required=True); r.add_argument("--limit", type=float, required=True); r.add_argument("--cwd", default=".")
    r.add_argument("--input", action="append", default=[]); r.add_argument("argv", nargs=argparse.REMAINDER)
    v = sub.add_parser("status"); v.add_argument("--watch", action="store_true")
    sub.add_parser("history"); sub.add_parser("doctor")
    args = p.parse_args(argv)
    try:
        root = Path(args.project).absolute()
        if root.is_symlink() or not root.is_dir():
            raise h.KitError("Project must be an existing non-symlink directory")
        root = root.resolve()
        if args.command == "doctor": return doctor()
        if args.command == "start": return start(root, args.minutes)
        if args.command == "event": return event(root, args.name, args.note)
        if args.command == "select": return select(root, args.engine, args.reason, args.alternative, args.evidence)
        if args.command == "worker":
            worker(root, args.id, args.status, args.task, args.files, args.next)
            print(render(root)); return 0
        if args.command == "run": return timed_run(root, args)
        if args.command == "history": return history(root)
        if args.command == "status":
            while True:
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
