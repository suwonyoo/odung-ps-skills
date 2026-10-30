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

The runtime suite passed 26 tests on Python 3.12.14/Linux. The four SKILL.md files also passed the skill format validator. Native discovery in a managed Codex CLI and the actual exam platform were not exercised.
