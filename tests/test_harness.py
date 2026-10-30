import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness as h

spec = importlib.util.spec_from_file_location("kit_install", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        h.init(self.root)
        (self.root / "app.py").write_text("VALUE = 3\n")
        self.task = {
            "schema_version": 1, "title": "Synthetic validation", "requirements": [
                {"id": "R1", "description": "Result equals three", "acceptance": "VALUE is three", "required": True}],
            "deliverables": [{"path": "app.py", "purpose": "Application", "required": True}],
            "checks": [{"id": "unit", "description": "Check expected value", "argv": [sys.executable, "-c", "import app; assert app.VALUE == 3"],
                        "cwd": ".", "timeout_seconds": 10, "requirements": ["R1"], "expected": "Assertion passes"}],
            "manual_checks": [],
        }
        self.save()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)
        self.temp.cleanup()

    def save(self):
        h.write_json(h.work(self.root) / "task.json", self.task)

    def state(self):
        return h.audit_result(self.root)

    def test_unrun_is_not_verified(self):
        result = self.state()
        self.assertFalse(result["local_checks_satisfied"])
        self.assertEqual(result["checks"][0]["state"], "not_run")

    def test_actual_pass_and_nonempty_log(self):
        self.assertEqual(h.check_command(self.root, []), 0)
        result = self.state()
        self.assertTrue(result["local_checks_satisfied"])
        record = h.load_json(next((h.work(self.root) / "evidence").glob("*.json")))
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["argv"], self.task["checks"][0]["argv"])
        self.assertTrue((self.root / record["log"]).exists())

    def test_exit_code_and_failure_are_preserved(self):
        self.task["checks"][0]["argv"] = [sys.executable, "-c", "print('known failure'); raise SystemExit(7)"]
        self.save()
        self.assertEqual(h.check_command(self.root, []), 7)
        self.assertEqual(self.state()["checks"][0]["state"], "fail")
        self.assertIn("known failure", next((h.work(self.root) / "evidence").glob("*.log")).read_text())

    def test_failed_then_fixed_keeps_both_records(self):
        (self.root / "app.py").write_text("VALUE = 100\n")
        self.assertNotEqual(h.check_command(self.root, []), 0)
        (self.root / "app.py").write_text("VALUE = 3\n")
        self.assertEqual(h.check_command(self.root, []), 0)
        self.assertTrue(self.state()["local_checks_satisfied"])
        entries = list((h.work(self.root) / "evidence").glob("*.json"))
        self.assertEqual(len(entries), 2)
        self.assertEqual({h.load_json(p)["status"] for p in entries}, {"pass", "fail"})

    def test_code_change_invalidates_prior_pass(self):
        h.check_command(self.root, [])
        (self.root / "app.py").write_text("VALUE = 4\n")
        self.assertEqual(self.state()["checks"][0]["state"], "stale")

    def test_criteria_change_invalidates_prior_pass(self):
        h.check_command(self.root, [])
        self.task["requirements"][0]["acceptance"] = "new criterion"
        self.save()
        self.assertEqual(self.state()["checks"][0]["state"], "stale")

    def test_check_that_changes_source_is_stale(self):
        self.task["checks"][0]["argv"] = [sys.executable, "-c", "from pathlib import Path; Path('new_source.py').write_text('x=1')"]
        self.save()
        self.assertEqual(h.check_command(self.root, []), 0)
        self.assertEqual(self.state()["checks"][0]["state"], "stale")

    def test_evidence_log_change_is_invalid(self):
        h.check_command(self.root, [])
        next((h.work(self.root) / "evidence").glob("*.log")).write_text("edited")
        self.assertEqual(self.state()["checks"][0]["state"], "invalid_evidence")

    def test_timeout_is_not_pass(self):
        self.task["checks"][0].update(argv=[sys.executable, "-c", "import time; time.sleep(20)"], timeout_seconds=1)
        self.save()
        self.assertEqual(h.check_command(self.root, []), 124)
        self.assertFalse(self.state()["local_checks_satisfied"])

    def test_log_limit_is_failure(self):
        self.task["checks"][0]["argv"] = [sys.executable, "-c", "print('x' * 1000)"]
        self.save()
        with mock.patch.object(h, "MAX_LOG_BYTES", 100):
            self.assertEqual(h.check_command(self.root, []), 125)
        self.assertEqual(next((h.work(self.root) / "evidence").glob("*.log")).stat().st_size, 100)

    def test_nonexistent_command_is_recorded(self):
        self.task["checks"][0]["argv"] = ["this-command-does-not-exist-kit-test"]
        self.save()
        self.assertEqual(h.check_command(self.root, []), 127)
        self.assertEqual(self.state()["checks"][0]["state"], "fail")

    def test_manual_requires_user_confirmation(self):
        self.task["manual_checks"] = [{"id": "ui", "description": "Person sees the result", "requirements": ["R1"], "expected": "Three on screen"}]
        self.save()
        h.check_command(self.root, [])
        args = argparse.Namespace(id="ui", status="pass", observed="Saw three", user_confirmed=False)
        with self.assertRaises(h.KitError): h.manual(self.root, args)
        self.assertFalse(self.state()["local_checks_satisfied"])
        args.user_confirmed = True
        h.manual(self.root, args)
        self.assertEqual(self.state()["checks"][1]["state"], "user_reported_pass")
        self.assertTrue(self.state()["local_checks_satisfied"])

    def test_missing_or_empty_required_file_blocks_audit(self):
        self.task["deliverables"].append({"path": "README.md", "purpose": "Run guide", "required": True})
        self.save()
        h.check_command(self.root, [])
        self.assertFalse(self.state()["local_checks_satisfied"])
        (self.root / "README.md").touch()
        h.check_command(self.root, [])
        self.assertEqual(self.state()["deliverables"][1]["state"], "missing_or_empty")

    def test_no_checks_and_unknown_references_fail_configuration(self):
        self.task["checks"][0]["requirements"] = ["MISSING"]
        self.save()
        with self.assertRaises(h.KitError): h.validate_task(self.root)
        self.task["checks"] = []
        self.save()
        with self.assertRaises(h.KitError): h.validate_task(self.root)

    def test_required_requirement_cannot_lack_coverage(self):
        self.task["requirements"].append({"id": "R2", "description": "More work", "acceptance": "More work checked", "required": True})
        self.save()
        with self.assertRaises(h.KitError): h.validate_task(self.root)

    def test_schema_typos_are_not_silently_ignored(self):
        self.task["check"] = []
        self.save()
        with self.assertRaises(h.KitError): h.validate_task(self.root)

    def test_close_blocks_checks_manual_reports_and_preserves_state(self):
        h.close(self.root)
        for action in (lambda: h.check_command(self.root, []), lambda: h.report(self.root)):
            with self.assertRaises(h.KitError): action()
        h.init(self.root)
        self.assertEqual(h.load_json(h.work(self.root) / "state.json")["phase"], "closed")

    def test_report_does_not_make_source_evidence_stale(self):
        h.check_command(self.root, [])
        self.assertEqual(h.report(self.root), 0)
        self.assertTrue(self.state()["local_checks_satisfied"])
        self.assertIn("Local verification", (h.work(self.root) / "verification.md").read_text())

    def test_path_traversal_and_symlinks_are_rejected(self):
        for path in ("../outside", "/tmp/outside", "a/../../outside", "C:\\outside", "."):
            with self.assertRaises(h.KitError): h.safe_path(self.root, path)
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(h.KitError): h.safe_path(self.root, "linked/file")
        with self.assertRaises(h.KitError): h.snapshot(self.root)

    def test_cli_returns_actual_failure_code(self):
        self.task["checks"][0]["argv"] = [sys.executable, "-c", "raise SystemExit(9)"]
        self.save()
        p = subprocess.run([sys.executable, str(ROOT / "harness.py"), "--project", str(self.root), "check"], capture_output=True)
        self.assertEqual(p.returncode, 9)


class Installation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()

    def tearDown(self):
        self.stdout.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_dry_run_writes_nothing(self):
        self.assertEqual(installer.install(self.target), 0)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_install_preserves_existing_instructions_and_is_idempotent(self):
        (self.target / "AGENTS.md").write_text("existing project rules")
        (self.target / "README.md").write_text("existing task")
        installer.install(self.target, True)
        installer.install(self.target, True)
        self.assertEqual((self.target / "AGENTS.md").read_text(), "existing project rules")
        self.assertEqual((self.target / "README.md").read_text(), "existing task")
        self.assertTrue((self.target / ".harness/runner.py").is_file())
        self.assertEqual(len(list((self.target / ".agents/skills").glob("*/SKILL.md"))), 4)

    def test_conflict_is_preflighted_without_partial_installation(self):
        path = self.target / ".agents/skills/hackathon-finish/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("custom skill")
        with self.assertRaises(h.KitError): installer.install(self.target, True)
        self.assertFalse((self.target / ".harness").exists())
        self.assertEqual(path.read_text(), "custom skill")

    def test_file_parent_conflict_is_preflighted(self):
        (self.target / ".agents").write_text("not a directory")
        with self.assertRaises(h.KitError): installer.install(self.target, True)
        self.assertFalse((self.target / ".harness").exists())

    def test_symlink_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.target / ".harness").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(h.KitError): installer.install(self.target, True)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_installed_runner_starts_unconfigured(self):
        installer.install(self.target, True)
        cmd = [sys.executable, str(self.target / ".harness/runner.py"), "--project", str(self.target)]
        self.assertEqual(subprocess.run(cmd + ["init"], capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(cmd + ["audit"], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
