import argparse
import contextlib
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness as h
import workflow as w
from fixtures import intake, build_ready, verify_phase


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stdout = contextlib.redirect_stdout(io.StringIO()); self.stdout.__enter__()
        w.start(self.root, 180)
        (self.root / "app.py").write_text("VALUE = 3\n")
        self.task = {"schema_version": 1, "title": "Synthetic assignment", "requirements": [
            {"id": "R1", "description": "Return value three", "acceptance": "Value is three", "required": True}],
            "deliverables": [{"path": "app.py", "purpose": "Source", "required": True}],
            "checks": [{"id": "value", "description": "Expected small value", "argv": [sys.executable,"-c","import app; assert app.VALUE == 3"],
                        "cwd": ".", "timeout_seconds": 5, "requirements": ["R1"], "expected": "Value three"}], "manual_checks": []}
        h.write_json(w.path(self.root,"task.json"),self.task)

    def tearDown(self):
        self.stdout.__exit__(None,None,None); self.tmp.cleanup()

    def args(self, code, **kw):
        data=dict(argv=[sys.executable,"-c",code],session="solver",engine="baseline",label="test run",limit=3,cwd=".",input=[])
        data.update(kw); return argparse.Namespace(**data)

    def test_start_preserves_deadline_and_existing_decisions(self):
        before=w.read_state(self.root)
        w.path(self.root,"decisions.md").write_text("real decision")
        w.start(self.root,210)
        self.assertEqual(w.read_state(self.root)["deadline"],before["deadline"])
        self.assertEqual(w.path(self.root,"decisions.md").read_text(),"real decision")

    def test_contract_gate_needs_engine_real_requirements_and_fields(self):
        with self.assertRaises(h.KitError): w.event(self.root,"contract-ready","draft")
        intake(self.root)
        w.event(self.root,"inputs-reviewed","reviewed")
        w.select(self.root,"baseline","Simple problem","Solver unnecessary","observed")
        with self.assertRaises(h.KitError): w.event(self.root,"contract-ready","draft")
        c={"revision":"v1","owner":"core","requirement_ids":["R1"],"input":"JSON","output":"value","failure_behavior":"error"}
        h.write_json(w.path(self.root,"contract.json"),c)
        w.event(self.root,"contract-ready","reviewed")
        self.assertEqual(w.read_state(self.root)["phase"],"parallel-build")

    def test_verified_requires_current_pass_not_just_process_success(self):
        w.timed_run(self.root,self.args("pass"))
        with self.assertRaises(h.KitError):w.event(self.root,"verified","process exited")
        verify_phase(self.root)
        w.worker(self.root,"solver","done","test run",[],"reviewed")
        h.check_command(self.root,[])
        w.event(self.root,"verified","current acceptance evidence")
        self.assertEqual(w.read_state(self.root)["phase"],"finish")
        (self.root/"app.py").write_text("VALUE = 4\n")
        with self.assertRaises(h.KitError):w.event(self.root,"verified","old pass")

    def test_file_overlap_rejected_and_ownership_survives_timed_run(self):
        w.worker(self.root,"solver","running","core",["src/core"],"check")
        with self.assertRaises(h.KitError):w.worker(self.root,"ui","running","other",["src/core/model.py"],"check")
        w.timed_run(self.root,self.args("pass"))
        state=h.load_json(w.path(self.root,"workers/solver.json"))
        self.assertEqual(state["files"],["src/core"])
        self.assertEqual(state["status"],"waiting")

    def test_running_worker_becomes_stale_without_inventing_completion(self):
        w.worker(self.root,"core","running","core",[],"model")
        f=w.path(self.root,"workers/core.json"); data=h.load_json(f)
        data["updated_at"]=w.stamp(w.utc()-timedelta(seconds=130));h.write_json(f,data)
        self.assertIn("stale (확인 필요)",w.render(self.root))
        self.assertEqual(h.load_json(f)["status"],"running")

    def test_timed_run_records_real_failure_and_does_not_advance_phase(self):
        result=w.timed_run(self.root,self.args("print('actual'); raise SystemExit(7)"))
        self.assertEqual(result,7)
        run=h.load_json(next(w.path(self.root,"runs").glob("*.json")))
        self.assertEqual(run["process_exit_code"],7)
        self.assertIn("actual",h.safe_path(self.root,run["log"]).read_text())
        self.assertEqual(w.read_state(self.root)["phase"],"intake")

    def test_timed_out_child_is_not_success(self):
        result=w.timed_run(self.root,self.args("import time; time.sleep(5)",limit=.15))
        self.assertEqual(result,124)
        run=h.load_json(next(w.path(self.root,"runs").glob("*.json")))
        self.assertEqual(run["reason"],"timeout")
        self.assertLess(run["duration_seconds"],2)
        self.assertEqual(h.load_json(w.path(self.root,"workers/solver.json"))["status"],"blocked")

    def test_missing_program_is_recorded(self):
        a=self.args("pass");a.argv=["missing-odung-test-executable"]
        self.assertEqual(w.timed_run(self.root,a),127)
        run=h.load_json(next(w.path(self.root,"runs").glob("*.json")))
        self.assertEqual(run["reason"],"launch_error")

    def test_busy_writer_does_not_overwrite_state(self):
        with w.locked(self.root):
            with self.assertRaises(h.KitError):w.event(self.root,"inputs-reviewed","conflict")
        self.assertEqual(w.read_state(self.root)["phase"],"intake")

    def test_closed_workspace_blocks_mutations_and_execution(self):
        h.close(self.root)
        for fn in [lambda:w.start(self.root,180), lambda:w.event(self.root,"inputs-reviewed","closed"),
                   lambda:w.timed_run(self.root,self.args("raise SystemExit(99)"))]:
            with self.assertRaises(h.KitError):fn()

    def test_tampered_timing_log_is_not_a_valid_sample(self):
        w.timed_run(self.root,self.args("print('sample')"))
        run=h.load_json(next(w.path(self.root,"runs").glob("*.json")))
        h.safe_path(self.root,run["log"]).write_text("edited")
        out=io.StringIO()
        with contextlib.redirect_stdout(out):w.history(self.root)
        self.assertIn("unknown",out.getvalue())

    def test_bad_budget_and_session_path_are_rejected(self):
        for x in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(h.KitError):w.positive(x,"budget")
        with self.assertRaises(h.KitError):w.worker(self.root,"../escape","running","x",[],"")

    def test_final_lock_conflict_can_be_recovered_from_completed_run(self):
        original=w.worker
        def contend(*args,**kwargs):
            if args[2] in ("waiting","blocked"):
                raise h.KitError("writer busy")
            return original(*args,**kwargs)
        with mock.patch.object(w,"worker",side_effect=contend):
            self.assertEqual(w.timed_run(self.root,self.args("pass")),0)
        raw=h.load_json(w.path(self.root,"workers/solver.json"))
        self.assertEqual(raw["status"],"running")
        self.assertEqual(w.effective_worker(self.root,raw)["status"],"waiting")
        self.assertEqual(w.timed_run(self.root,self.args("pass")),0)

    def test_after_snapshot_failure_preserves_original_command_exit(self):
        result=w.timed_run(self.root,self.args("from pathlib import Path; Path('linked').symlink_to('/tmp'); raise SystemExit(7)"))
        self.assertEqual(result,7)
        record=h.load_json(next(w.path(self.root,"runs").glob("*.json")))
        self.assertEqual(record["process_exit_code"],7)
        self.assertTrue(record["workspace_changed"])
        self.assertIn("snapshot_error",record)

    def test_cwd_and_declared_input_changes_do_not_merge_timings(self):
        (self.root/"a").mkdir();(self.root/"b").mkdir()
        w.timed_run(self.root,self.args("pass",cwd="a"))
        w.timed_run(self.root,self.args("pass",cwd="b"))
        runs=[h.load_json(f) for f in w.path(self.root,"runs").glob("*.json")]
        self.assertEqual(len({r["fingerprint"] for r in runs}),2)
        w.path(self.root,"input.json").write_text('{"value":1}')
        w.timed_run(self.root,self.args("from pathlib import Path; Path('.harness/work/input.json').write_text('{}')",input=[".harness/work/input.json"]))
        changed=[h.load_json(f) for f in w.path(self.root,"runs").glob("*.json") if h.load_json(f).get("input_sha256")]
        self.assertTrue(changed[0]["workspace_changed"])


class BusinessValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        example=ROOT/"examples/shift-assignment"
        spec=importlib.util.spec_from_file_location("business_validator",example/"validate.py")
        cls.validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.validator)
        cls.data=json.loads((example/"problem.json").read_text())

    def test_independent_validator_catches_plausible_but_invalid_plan(self):
        result={"input_version":"synthetic-1","assignments":[
            {"shift_id":"s1","employee_id":"A"},{"shift_id":"s2","employee_id":"A"},{"shift_id":"s3","employee_id":"B"}]}
        checked=self.validator.check(self.data,result)
        self.assertFalse(checked["valid"])
        self.assertIn("DAILY_CAPACITY:A",checked["violations"])
        self.assertIn("UNAVAILABLE:s3",checked["violations"])

    def test_stale_and_missing_assignments_are_not_publishable(self):
        checked=self.validator.check(self.data,{"input_version":"old","assignments":[]})
        self.assertIn("INPUT_VERSION_MISMATCH",checked["violations"])
        self.assertEqual(len([v for v in checked["violations"] if v.startswith("MISSING_SHIFT")]),3)

    def test_known_manual_assignment_has_zero_penalty(self):
        result={"input_version":"synthetic-1","assignments":[
            {"shift_id":"s1","employee_id":"B"},{"shift_id":"s2","employee_id":"C"},{"shift_id":"s3","employee_id":"A"}]}
        checked=self.validator.check(self.data,result)
        self.assertTrue(checked["valid"]);self.assertEqual(checked["preference_penalty"],0)
