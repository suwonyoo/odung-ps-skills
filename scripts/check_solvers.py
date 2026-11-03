#!/usr/bin/env python3
"""Optional real-runtime smoke checks; does not install or download anything."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/shift-assignment"
spec = importlib.util.spec_from_file_location("business_validator", EXAMPLE / "validate.py")
validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ortools-python")
    p.add_argument("--java")
    p.add_argument("--classpath-file", default=str(EXAMPLE/"timefold/classpath.txt"))
    args = p.parse_args()
    if not args.ortools_python and not args.java: p.error("Choose at least one prepared runtime")
    source = json.loads((EXAMPLE/"problem.json").read_text())
    impossible = json.loads((EXAMPLE/"impossible.json").read_text())
    missing = copy.deepcopy(source); del missing["shifts"][0]["day"]
    fractional = copy.deepcopy(source); fractional["shifts"][0]["day"] = 1.5
    engines = []
    if args.ortools_python:
        engines.append(("ortools-cp-sat", [args.ortools_python,str(EXAMPLE/"ortools/solve.py")]))
    if args.java:
        import os
        cp = str(EXAMPLE/"timefold/target/classes")+os.pathsep+Path(args.classpath_file).read_text().strip()
        engines.append(("timefold", [args.java,"-cp",cp,"local.odung.Main"]))
    failures = 0
    with tempfile.TemporaryDirectory(prefix="odung-solvers-") as directory:
        base = Path(directory)
        for engine, cmd in engines:
            for name, data in [("feasible", source), ("impossible", impossible), ("missing-day", missing), ("fractional-day", fractional)]:
                inp = base/(name+".json"); inp.write_text(json.dumps(data))
                out = base/(engine+"-"+name+".json")
                argv = cmd + ([str(inp),"--seconds","0.5","--output",str(out)] if engine == "ortools-cp-sat" else [str(inp),"0.5",str(out)])
                started = time.monotonic()
                run = subprocess.run(argv,capture_output=True,text=True,timeout=30)
                elapsed = time.monotonic()-started
                result = json.loads(out.read_text()) if out.exists() else None
                if name == "feasible":
                    valid = run.returncode == 0 and result is not None and validator.check(data,result)["valid"] and result["feasible"] and result["objective"] == 0
                elif name == "impossible":
                    valid = run.returncode == 3 and result is not None and not result["feasible"] and not validator.check(data,result)["valid"]
                    if valid and engine == "ortools-cp-sat": valid = result["raw_status"] == "INFEASIBLE" and result["infeasibility_proven"]
                    if valid and engine == "timefold": valid = not result["infeasibility_proven"] and not result["optimality_proven"]
                else:
                    valid = run.returncode != 0 and result is None
                failures += not valid
                print(json.dumps({"engine":engine,"case":name,"passed":bool(valid),"exit":run.returncode,"process_seconds":round(elapsed,3)},ensure_ascii=False),flush=True)
                if not valid: print((run.stdout+run.stderr)[-6000:])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
