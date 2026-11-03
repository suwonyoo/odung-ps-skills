# Validation

Validation is performed on synthetic temporary projects. No contest workspace, real problem, or private input is used.

Automated checks cover these behaviors:

- Dry-run installation writes no files; repeated installation is idempotent.
- Existing project instructions and application files remain intact.
- Conflicts and symlink paths stop installation before writing.
- Empty configuration, unknown references, missing coverage, and schema typos fail.
- Actual success and failure exits are captured, including launch errors and timeouts.
- Output exceeding the local log limit is recorded as failure.
- A fixed implementation retains the earlier failed record.
- Source changes, criteria changes, and changes during a check invalidate prior evidence.
- A changed log is marked invalid.
- A missing required file blocks local readiness.
- Manual checks require explicit user confirmation and remain labeled user-reported.
- Closing the work phase prevents additional checks and report generation.

Run the suite with `python3 -m unittest discover -s tests -v`.

These tests validate the runner's behavior. They do not prove that a task author's assertions cover every requirement. They do not validate a particular managed Codex release, a contest's grader, official submission, or model availability. Native skill discovery in the target environment must be checked there.

On 2026-10-30, a separate agent used `hackathon-verify` on a synthetic stock project without being told which defects were present. The original narrow test passed. The agent derived additional checks from the task, found an equal-threshold error and an empty-value error, and produced seven checks with two failures. It left the application unchanged, preserved both the earlier pass and later failure, and reported the optional UI check as unverified. This supports the verification workflow in that scenario; it does not establish a general success rate.

The v2 runtime suite passed 44 tests on Python 3.12/Linux on 2026-11-04 KST. All seven SKILL.md files passed the skill format validator. Native discovery in a managed Codex CLI and the actual exam platform were not exercised.

Additional v2 checks cover contract and evidence gates, overlapping file ownership, ownership preservation across timed commands, stale session display, real nonzero exits, outer timeout, missing programs, busy writers, recovery from a delayed final status update, failed post-run snapshots, differing working directories, modified declared inputs, changed timing logs, and closed workspaces. A process exit of zero cannot advance to verified without current configured acceptance evidence.

Both optional solver examples were actually executed: OR-Tools 9.15.6755 / Python 3.12 and Timefold CE 2.7.1 / Java 21. The Java sources compiled with Maven 3.9.11. Four scenarios per solver passed: feasible zero-preference-penalty assignment, an impossible input, missing day, and fractional day. The independent Python validator accepted the good plans and rejected the impossible plans. The malformed inputs were rejected before solving. Timefold's impossible candidate was not labeled proven infeasible or optimal.

Reproduce the optional checks after preparing the runtimes and compiling Timefold:

```bash
python3 scripts/check_solvers.py --ortools-python /path/to/venv/bin/python --java /path/to/jdk21/bin/java
```

An independent code review reproduced five faults in final-state recovery, result preservation, timing grouping, input freshness and Java input coercion. They were fixed, and the same reproductions passed afterward. A separate cold-start skill exercise used a synthetic meeting-room assignment brief: it produced requirements, model and contract drafts, manual stakeholder questions, decision/architecture/AI notes and a status board. It kept missing business priorities and unrun solver prototypes explicitly unresolved and did not send a DM or claim a completed application. This is a single preparation exercise, not a general success-rate estimate.

Limitations: the examples implement only their stated synthetic rules; they are not production services. No universal automatic problem-to-model compiler, native CLI hook installation, solver worker scheduler, real task grader, UI submission, or production transaction system is tested or claimed. A real application must implement its own independent rule checks, version-aware publication and fallback behavior. Timing history is descriptive, not an ETA guarantee. Dependency installation time is environment-dependent; top-level pins are not full transitive lockfiles.
