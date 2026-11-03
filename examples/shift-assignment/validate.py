#!/usr/bin/env python3
"""Independent business checks. Does not import either solver or its constraints."""
import argparse
import json
from pathlib import Path


def validate_input(data):
    if not isinstance(data, dict) or set(data) != {"input_version", "employees", "shifts"}:
        raise ValueError("Expected input_version, employees and shifts")
    if not isinstance(data["input_version"], str) or not data["input_version"]:
        raise ValueError("input_version must be a nonempty string")
    for group in ("employees", "shifts"):
        if not isinstance(data[group], list) or not data[group]:
            raise ValueError(group + " must be a nonempty list in this example")
        ids = [x.get("id") for x in data[group]]
        if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
            raise ValueError(group + " IDs must be unique nonempty strings")
    for e in data["employees"]:
        if set(e) != {"id", "skills", "unavailable_days"}:
            raise ValueError("Unsupported employee fields")
        if not isinstance(e["skills"], list) or any(not isinstance(x, str) or not x for x in e["skills"]):
            raise ValueError("skills must be strings")
        if not isinstance(e["unavailable_days"], list) or any(type(x) is not int or not -(2**31) <= x < 2**31 for x in e["unavailable_days"]):
            raise ValueError("unavailable_days must be integers")
    known = {e["id"] for e in data["employees"]}
    for s in data["shifts"]:
        if set(s) != {"id", "day", "skill", "preferred_employee"} or type(s["day"]) is not int or not -(2**31) <= s["day"] < 2**31:
            raise ValueError("Unsupported shift fields or day type")
        if not isinstance(s["skill"], str) or not s["skill"] or s["preferred_employee"] not in known:
            raise ValueError("Invalid skill or preferred_employee")


def check(data, result):
    validate_input(data)
    errors = []
    if result.get("input_version") != data["input_version"]:
        errors.append("INPUT_VERSION_MISMATCH")
    employees = {e["id"]: e for e in data["employees"]}
    shifts = {s["id"]: s for s in data["shifts"]}
    assignments = result.get("assignments", [])
    if not isinstance(assignments, list):
        return {"valid": False, "violations": ["ASSIGNMENTS_NOT_LIST"], "preference_penalty": None}
    seen, occupied, penalty = set(), set(), 0
    for a in assignments:
        if not isinstance(a, dict) or set(a) != {"shift_id", "employee_id"}:
            errors.append("INVALID_ASSIGNMENT"); continue
        sid, eid = a["shift_id"], a["employee_id"]
        if sid not in shifts or eid not in employees:
            errors.append("UNKNOWN_ID"); continue
        if sid in seen:
            errors.append("DUPLICATE_SHIFT:" + sid)
        seen.add(sid)
        s, e = shifts[sid], employees[eid]
        if s["skill"] not in e["skills"]:
            errors.append("SKILL:" + sid)
        if s["day"] in e["unavailable_days"]:
            errors.append("UNAVAILABLE:" + sid)
        slot = (eid, s["day"])
        if slot in occupied:
            errors.append("DAILY_CAPACITY:" + eid)
        occupied.add(slot)
        penalty += eid != s["preferred_employee"]
    errors.extend("MISSING_SHIFT:" + sid for sid in sorted(set(shifts) - seen))
    return {"valid": not errors, "violations": errors, "preference_penalty": penalty}


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("result")
    a = p.parse_args()
    try:
        report = check(json.loads(Path(a.input).read_text()), json.loads(Path(a.result).read_text()))
        print(json.dumps(report, indent=2)); raise SystemExit(0 if report["valid"] else 1)
    except (ValueError, KeyError, TypeError) as e:
        print(json.dumps({"valid": False, "error": str(e)})); raise SystemExit(2)
