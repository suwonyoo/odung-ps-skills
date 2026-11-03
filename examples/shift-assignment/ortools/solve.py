#!/usr/bin/env python3
"""Synthetic assignment adapter. No universal scheduling model is implied."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from ortools.sat.python import cp_model
import ortools

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate import check, validate_input


def solve(data, seconds, workers=1):
    if not math.isfinite(seconds) or seconds <= 0 or type(workers) is not int or workers < 1:
        raise ValueError("Positive finite seconds and positive integer workers required")
    started = time.monotonic()
    validate_input(data)
    model = cp_model.CpModel()
    variables = {}
    for s in data["shifts"]:
        for e in data["employees"]:
            v = model.new_bool_var(f"{s['id']}__{e['id']}")
            variables[s["id"], e["id"]] = v
            if s["skill"] not in e["skills"] or s["day"] in e["unavailable_days"]:
                model.add(v == 0)
        model.add_exactly_one(variables[s["id"], e["id"]] for e in data["employees"])
    for e in data["employees"]:
        for day in {s["day"] for s in data["shifts"]}:
            model.add_at_most_one(variables[s["id"], e["id"]] for s in data["shifts"] if s["day"] == day)
    model.minimize(sum(v for (sid, eid), v in variables.items()
                       if eid != next(s["preferred_employee"] for s in data["shifts"] if s["id"] == sid)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 0
    model_seconds = time.monotonic() - started

    class Progress(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__(); self.first = None; self.last = None; self.best = None
        def on_solution_callback(self):
            t = time.monotonic() - solving
            if self.first is None: self.first = t
            if self.best is None or self.objective_value < self.best:
                self.best = self.objective_value; self.last = t

    progress = Progress()
    solving = time.monotonic()
    status = solver.solve(model, progress)
    solve_seconds = time.monotonic() - solving
    has_solution = status in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    result = {"schema_version": 1, "engine": "ortools-cp-sat", "engine_version": ortools.__version__,
              "input_version": data["input_version"], "raw_status": solver.status_name(status),
              "has_solution": has_solution, "optimality_proven": status == cp_model.OPTIMAL,
              "infeasibility_proven": status == cp_model.INFEASIBLE,
              "assignments": [{"shift_id": sid, "employee_id": eid} for (sid,eid),v in variables.items()
                              if has_solution and solver.value(v)],
              "objective": solver.objective_value if has_solution else None,
              "objective_bound": solver.best_objective_bound if has_solution else None,
              "limits": {"solver_seconds": seconds, "workers": workers, "seed": 0},
              "timing": {"model_seconds": model_seconds, "solve_seconds": solve_seconds,
                         "first_feasible_seconds": progress.first, "last_improvement_seconds": progress.last}}
    validating = time.monotonic()
    result["validation"] = check(data, result)
    result["feasible"] = has_solution and result["validation"]["valid"]
    result["timing"]["validation_seconds"] = time.monotonic() - validating
    result["timing"]["adapter_seconds"] = time.monotonic() - started
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("--seconds", type=float, default=3)
    p.add_argument("--workers", type=int, default=1); p.add_argument("--output")
    a = p.parse_args(); start = time.monotonic()
    try:
        raw = Path(a.input).read_bytes()
        result = solve(json.loads(raw), a.seconds, a.workers)
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        result["timing"]["total_seconds"] = time.monotonic() - start
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if a.output: Path(a.output).write_text(text + "\n", encoding="utf-8")
        print(text)
        raise SystemExit(0 if result["feasible"] else 3)
    except (ValueError, KeyError, TypeError) as e:
        print(json.dumps({"raw_status": "INVALID_INPUT", "error": str(e)})); raise SystemExit(2)
