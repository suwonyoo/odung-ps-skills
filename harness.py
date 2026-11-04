#!/usr/bin/env python3
"""Local task checks and evidence. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

# Keep one exception class when the CLI imports coordination during execution.
if __name__ == '__main__':
    sys.modules.setdefault(Path(__file__).stem, sys.modules[__name__])

VERSION = "3.3.0"
IGNORED_DIRS = {".git", ".harness", "node_modules", ".venv", "venv", "__pycache__",
                ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", "target", ".next", "coverage"}
MAX_LOG_BYTES = 8 * 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class KitError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_path(root, relative, *, allow_dot=False):
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise KitError(f"Invalid relative path: {relative!r}")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or ":" in relative:
        raise KitError(f"Path must stay inside project: {relative!r}")
    if str(parts) == "." and not allow_dot:
        raise KitError("Expected a file path, not the project root")
    target = root / parts
    current = root
    for component in parts.parts:
        current = current / component
        if current.is_symlink():
            raise KitError(f"Symlink paths are not supported: {relative}")
    return target


def load_json(path):
    if path.is_symlink():
        raise KitError(f"Refusing symlink JSON: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise KitError(f"Cannot read JSON {path.name}: {e}") from e


def write_json(path, data, *, exclusive=False):
    if path.is_symlink():
        raise KitError(f"Refusing symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as f:
            f.write(text)
        return
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temp.open("x", encoding="utf-8") as f:
            f.write(text)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def work(root):
    return safe_path(root, ".harness/work")


def require_working(root):
    state = load_json(work(root) / "state.json")
    if state.get("phase") != "working":
        raise KitError("Work records are closed. No further checks, reports, or edits through this tool.")
    return state


def init(root):
    base = work(root)
    base.mkdir(parents=True, exist_ok=True)
    if (base / "state.json").exists():
        print("Already initialized; existing task and evidence preserved.")
        return 0
    for name in ("task.json", "decisions.md", "handoff.md"):
        dest = safe_path(root, f".harness/work/{name}")
        if dest.exists():
            raise KitError(f"Existing {dest.name}; inspect it before initializing")
    task = {"schema_version": 1, "title": "", "requirements": [], "deliverables": [],
            "checks": [], "manual_checks": []}
    write_json(base / "task.json", task, exclusive=True)
    (base / "decisions.md").write_text(
        "# Decisions\n\nRecord only actual decisions: time, issue, alternatives, choice, reason, next check.\n",
        encoding="utf-8")
    (base / "handoff.md").write_text(
        "# Handoff\n\nFill from actual work: purpose, run command, inputs, outputs, evidence, limitations.\n",
        encoding="utf-8")
    write_json(base / "state.json", {"schema_version": 1, "phase": "working", "created_at": now()}, exclusive=True)
    print("Created .harness/work/task.json. Configure actual requirements before checking.")
    return 0


def nonempty_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise KitError(f"{label} must be non-empty text")


def validate_task(root):
    path = safe_path(root, ".harness/work/task.json")
    task = load_json(path)
    fields = {"schema_version", "title", "requirements", "deliverables", "checks", "manual_checks"}
    if not isinstance(task, dict) or set(task) != fields or task["schema_version"] != 1:
        raise KitError("task.json must have exactly schema_version=1, title, requirements, deliverables, checks, manual_checks")
    nonempty_string(task["title"], "title")
    for name in fields - {"schema_version", "title"}:
        if not isinstance(task[name], list):
            raise KitError(f"{name} must be an array")
    if not task["requirements"] or not task["deliverables"]:
        raise KitError("Task is not configured: add actual requirements and deliverables")
    if not task["checks"] and not task["manual_checks"]:
        raise KitError("Task is unverified: configure at least one check")
    specs = {
        "requirements": {"id", "description", "acceptance", "required"},
        "deliverables": {"path", "purpose", "required"},
        "checks": {"id", "description", "argv", "cwd", "timeout_seconds", "requirements", "expected"},
        "manual_checks": {"id", "description", "requirements", "expected"},
    }
    req_ids, check_ids, paths = set(), set(), set()
    for group in ("requirements", "deliverables", "checks", "manual_checks"):
        for item in task[group]:
            if not isinstance(item, dict) or set(item) != specs[group]:
                raise KitError(f"Wrong fields in {group}; expected {sorted(specs[group])}")
            if "id" in item:
                if not isinstance(item["id"], str) or not ID_RE.fullmatch(item["id"]):
                    raise KitError(f"Invalid ID in {group}")
                seen = req_ids if group == "requirements" else check_ids
                if item["id"] in seen:
                    raise KitError(f"Duplicate ID: {item['id']}")
                seen.add(item["id"])
            for key in ("description", "acceptance", "purpose", "expected"):
                if key in item:
                    nonempty_string(item[key], key)
            if "required" in item and type(item["required"]) is not bool:
                raise KitError("required must be true or false")
            if group == "deliverables":
                safe_path(root, item["path"])
                if item["path"] in paths:
                    raise KitError("Duplicate deliverable path")
                if PurePosixPath(item["path"]).parts[0] in {".git", ".harness"}:
                    raise KitError("Map deliverables to the actual task paths, outside .git and .harness")
                paths.add(item["path"])
            if group in {"checks", "manual_checks"}:
                refs = item["requirements"]
                if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in req_ids for r in refs):
                    raise KitError(f"Check {item['id']} must reference known requirements")
            if group == "checks":
                argv = item["argv"]
                if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or "\x00" in a for a in argv):
                    raise KitError("argv must be a non-empty array of non-empty strings")
                safe_path(root, item["cwd"], allow_dot=True)
                t = item["timeout_seconds"]
                if type(t) is not int or not 1 <= t <= 600:
                    raise KitError("timeout_seconds must be an integer from 1 to 600")
    covered = {r for c in task["checks"] + task["manual_checks"] for r in c["requirements"]}
    missing = [r["id"] for r in task["requirements"] if r["required"] and r["id"] not in covered]
    if missing:
        raise KitError(f"Required requirements have no checks: {', '.join(missing)}")
    return task


def snapshot(root):
    from coordination import context_signature
    h = hashlib.sha256()
    count = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for d in dirs:
            if (Path(parent) / d).is_symlink():
                raise KitError(f"Source snapshot cannot follow symlink: {(Path(parent) / d).relative_to(root)}")
        for filename in sorted(files):
            path = Path(parent) / filename
            if filename.endswith((".pyc", ".pyo")) or filename == ".DS_Store":
                continue
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                raise KitError(f"Unsupported source entry: {rel}")
            count += 1
            if count > 20000:
                raise KitError("Source snapshot exceeds 20,000 files; use a focused task workspace")
            h.update(rel.encode("utf-8") + b"\0" + digest_file(path).encode() + b"\n")
    # Explicit deliverables remain evidence-bearing even under ignored build dirs.
    task = load_json(work(root) / 'task.json')
    artifacts = {}
    for spec in task.get('deliverables', []):
        target = safe_path(root, spec['path'])
        artifacts[spec['path']] = digest_file(target) if target.is_file() else None
    return {"sources_sha256": h.hexdigest(), "task_sha256": digest_file(work(root) / "task.json"),
            "context_sha256": context_signature(root),
            "deliverables_sha256": digest_bytes(json.dumps(artifacts, sort_keys=True).encode()), "source_files": count}


def same_snapshot(a, b):
    return all(a.get(k) == b.get(k) for k in ("sources_sha256", "task_sha256", "context_sha256", "deliverables_sha256"))


def stop_process(proc):
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        pass
    proc.wait()


def run_check(root, check):
    before = snapshot(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    evidence = safe_path(root, ".harness/work/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    log = evidence / (run_id + ".log")
    record = {"schema_version": 1, "runner_version": VERSION, "run_id": run_id,
              "check_id": check["id"], "kind": "command", "actor": "command-runner",
              "started_at": now(), "argv": check["argv"], "cwd": check["cwd"],
              "requirements": check["requirements"], "expected": check["expected"],
              "before": before, "log": log.relative_to(root).as_posix()}
    start = time.monotonic()
    reason = "completed"
    print(f"RUN {check['id']}", flush=True)
    proc, exit_code = None, 127
    try:
        with log.open("xb") as output:
            try:
                proc = subprocess.Popen(check["argv"], cwd=safe_path(root, check["cwd"], allow_dot=True),
                                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                        start_new_session=os.name == "posix")
                while proc.poll() is None:
                    if time.monotonic() - start >= check["timeout_seconds"]:
                        reason = "timeout"
                        stop_process(proc)
                        break
                    if log.stat().st_size > MAX_LOG_BYTES:
                        reason = "output_limit"
                        stop_process(proc)
                        break
                    time.sleep(0.04)
                exit_code = proc.wait()
            except OSError as e:
                if proc is None:
                    exit_code, reason = 127, 'launch_error'
                else:
                    stop_process(proc)
                    exit_code, reason = proc.returncode, 'supervisor_error'
                output.write((str(e) + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        reason = 'interrupted'
        if proc is not None:
            stop_process(proc)
            exit_code = proc.returncode
    except BaseException:
        reason = 'interrupted'
        if proc is not None:
            stop_process(proc)
            exit_code = proc.returncode
        raise
    finally:
        if log.exists() and log.stat().st_size > MAX_LOG_BYTES:
            with log.open("r+b") as f:
                f.truncate(MAX_LOG_BYTES)
            reason = "output_limit"
        try:
            after = snapshot(root)
            changed = not same_snapshot(before, after)
        except (KitError, OSError, ValueError) as exc:
            after, changed = None, True
            record['snapshot_error'] = str(exc)
        reported_exit = {'timeout':124, 'output_limit':125, 'supervisor_error':125, 'interrupted':130}.get(reason, exit_code)
        if reported_exit < 0:
            reported_exit = 128 - reported_exit
        if reported_exit == 0 and 'snapshot_error' in record:
            reported_exit = 2  # Process succeeded; evidence capture did not.
        record.update({"finished_at": now(), "duration_seconds": round(time.monotonic() - start, 3),
                       "exit_code": reported_exit, "process_exit_code": exit_code, "reason": reason,
                       "status": "pass" if reported_exit == 0 else "fail", "after": after,
                       "workspace_changed": changed, "log_sha256": digest_file(log) if log.exists() else None})
        write_json(evidence / (run_id + ".json"), record, exclusive=True)
    print(f"{record['status'].upper()} {check['id']}: exit={reported_exit}; {record['log']}")
    return reported_exit


def check_command(root, ids):
    require_working(root)
    task = validate_task(root)
    choices = {c["id"]: c for c in task["checks"]}
    if ids and set(ids) - choices.keys():
        raise KitError(f"Unknown command check: {sorted(set(ids) - choices.keys())}")
    selected = [choices[i] for i in ids] if ids else list(choices.values())
    if not selected:
        raise KitError("No automated checks configured; manual observations remain unverified")
    first_failure = 0
    for check in selected:
        result = run_check(root, check)
        if result and not first_failure:
            first_failure = result
    return first_failure


def manual(root, args):
    require_working(root)
    task = validate_task(root)
    checks = {c["id"]: c for c in task["manual_checks"]}
    if args.id not in checks:
        raise KitError("Unknown manual check ID")
    if not args.user_confirmed:
        raise KitError("Use --user-confirmed only after the user explicitly reports the observation")
    nonempty_string(args.observed, "observed")
    check = checks[args.id]
    stamp = snapshot(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    data = {"schema_version": 1, "runner_version": VERSION, "run_id": run_id, "check_id": args.id,
            "kind": "manual", "actor": "user-reported", "status": args.status,
            "requirements": check["requirements"], "expected": check["expected"],
            "observed": args.observed, "started_at": now(), "finished_at": now(),
            "before": stamp, "after": stamp, "workspace_changed": False}
    write_json(safe_path(root, f".harness/work/evidence/{run_id}.json"), data, exclusive=True)
    print(f"Recorded user-reported observation for {args.id}; this is not independent authentication.")
    return 0


def evidence_status(root, task):
    current = snapshot(root)
    latest = {}
    evidence = safe_path(root, ".harness/work/evidence")
    if evidence.exists():
        records = []
        for path in sorted(evidence.glob("*.json")):
            if path.is_symlink():
                raise KitError("Evidence files must not be symlinks")
            entry = load_json(path)
            if not isinstance(entry, dict) or not isinstance(entry.get("check_id"), str):
                raise KitError(f"Malformed evidence file: {path.name}")
            records.append((path.stat().st_mtime_ns, path.name, entry))
        for _, _, entry in sorted(records):
            latest[entry["check_id"]] = entry
    rows = []
    for spec in task["checks"] + task["manual_checks"]:
        entry = latest.get(spec["id"])
        state = "not_run"
        if entry:
            if entry.get("workspace_changed") or not same_snapshot(entry.get("after", {}), current):
                state = "stale"
            elif entry.get("kind") == "command":
                log = safe_path(root, entry.get("log", ""))
                if not log.is_file() or digest_file(log) != entry.get("log_sha256"):
                    state = "invalid_evidence"
                elif entry.get("status") == "pass" and entry.get("exit_code") == 0:
                    state = "pass"
                else:
                    state = "fail"
            elif entry.get("kind") == "manual" and entry.get("actor") == "user-reported":
                state = "user_reported_pass" if entry.get("status") == "pass" else "user_reported_fail"
            else:
                state = "invalid_evidence"
        rows.append({"id": spec["id"], "description": spec["description"], "requirements": spec["requirements"],
                     "state": state, "evidence": entry.get("run_id") if entry else None,
                     "kind": "command" if spec in task["checks"] else "manual"})
    return rows


def audit_result(root):
    from coordination import readiness_errors
    task = validate_task(root)
    rows = evidence_status(root, task)
    artifacts = []
    for spec in task["deliverables"]:
        path = safe_path(root, spec["path"])
        state = "present" if path.is_file() and path.stat().st_size else "missing_or_empty"
        artifacts.append({**spec, "state": state})
    requirements = []
    for req in task["requirements"]:
        checks = [c for c in rows if req["id"] in c["requirements"]]
        ok = bool(checks) and all(c["state"] in {"pass", "user_reported_pass"} for c in checks)
        requirements.append({**req, "state": "checks_satisfied" if ok else "not_verified"})
    ok = (all(r["state"] == "checks_satisfied" for r in requirements if r["required"])
          and all(d["state"] == "present" for d in artifacts if d["required"]))
    workflow_errors = readiness_errors(root)
    return {"title": task["title"], "checked_at": now(), "local_checks_satisfied": ok and not workflow_errors,
            "workflow_errors": workflow_errors,
            "requirements": requirements, "checks": rows, "deliverables": artifacts,
            "notice": "Local checks only. This is not official submission, grading, or proof of every behavior."}


def audit(root, as_json=False):
    result = audit_result(root)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for c in result["checks"]:
            print(f"{c['state']:20} {c['id']} {c['description']}")
        for d in result["deliverables"]:
            print(f"{d['state']:20} {d['path']}")
        for error in result['workflow_errors']:
            print('WORKFLOW BLOCKED     ' + error)
        print("LOCAL CHECKS SATISFIED" if result["local_checks_satisfied"] else "NOT VERIFIED / MISSING")
        print(result["notice"])
    return 0 if result["local_checks_satisfied"] else 1


def md_cell(text):
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def report(root):
    require_working(root)
    result = audit_result(root)
    lines = [f"# Local verification: {md_cell(result['title'])}", "", result["notice"], "",
             f"Generated: {result['checked_at']}", "", "| Check | Result | Evidence ID |", "|---|---|---|"]
    for c in result["checks"]:
        lines.append(f"| {md_cell(c['id'])} | {c['state']} | {c['evidence'] or 'none'} |")
    lines += ["", "| Requirement | Status | Acceptance |", "|---|---|---|"]
    for r in result["requirements"]:
        lines.append(f"| {md_cell(r['id'])} | {r['state']} | {md_cell(r['acceptance'])} |")
    lines += ["", "| Deliverable | Present |", "|---|---|"]
    for d in result["deliverables"]:
        lines.append(f"| {md_cell(d['path'])} | {d['state']} |")
    if result['workflow_errors']:
        lines += ['', '## Workflow blockers', '', *['- ' + md_cell(x) for x in result['workflow_errors']]]
    lines += ["", "Manual results are explicitly user-reported. Unrun and stale checks remain unverified.",
              "Copy only the required content to the actual submission paths and audit again after edits.", ""]
    path = safe_path(root, ".harness/work/verification.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path.relative_to(root))
    return 0 if result["local_checks_satisfied"] else 1


def close(root):
    state = require_working(root)
    state.update({"phase": "closed", "closed_at": now()})
    write_json(work(root) / "state.json", state)
    print("Local records closed. Stop AI assistance before a no-AI phase. No official submission was performed.")
    return 0


def doctor(root):
    print(f"Kit {VERSION}; Python {sys.version.split()[0]}; project {root}")
    for executable in ("git", "node", "codex"):
        path = shutil.which(executable)
        if not path:
            print(f"{executable}: not found")
            continue
        try:
            proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8)
            text = (proc.stdout or proc.stderr).strip().splitlines()
            print(f"{executable}: {text[0][:200] if text else 'no version output'}")
        except (OSError, subprocess.TimeoutExpired):
            print(f"{executable}: version check unavailable")
    print("Confirm /status and /model manually in the provided Codex. Do not change platform credentials or policies.")
    print("No environment variables, credentials, processes, or remote services were inspected.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Task workspace (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "doctor", "report", "close"):
        sub.add_parser(name)
    c = sub.add_parser("check")
    c.add_argument("ids", nargs="*")
    a = sub.add_parser("audit")
    a.add_argument("--json", action="store_true")
    m = sub.add_parser("manual")
    m.add_argument("--id", required=True)
    m.add_argument("--status", choices=("pass", "fail"), required=True)
    m.add_argument("--observed", required=True)
    m.add_argument("--user-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path(args.project).absolute()
        if root.is_symlink() or not root.is_dir():
            raise KitError("Project must be an existing non-symlink directory")
        root = root.resolve()
        safe_path(root, ".harness")
        if args.command == "init": return init(root)
        if args.command == "doctor": return doctor(root)
        if args.command == "check": return check_command(root, args.ids)
        if args.command == "manual": return manual(root, args)
        if args.command == "audit": return audit(root, args.json)
        if args.command == "report": return report(root)
        if args.command == "close": return close(root)
    except (KitError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
