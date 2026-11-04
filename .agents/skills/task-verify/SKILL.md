---
name: task-verify
description: Validate implemented behavior in an active structured task workflow using real command output and clearly attributed user observations. Preserve failures and unknowns before claiming completion. No competition context is required. Respect an actual no-AI assessment restriction.
---

Read the task, project instructions, `.harness/GUIDE.md`, and `.harness/work/task.json` when present. Do not call an absent runner. Respect a closed work phase and stop if the user has entered a no-AI assessment.

1. Map required behaviors to checks. Confirm each expected result comes from the task, a trusted reference, or a separately reasoned small example. Review the test assertion; a command returning zero without checking the requirement is insufficient.
2. Select normal, boundary, and invalid input cases where they matter. Do not add ceremonial tests that repeat the implementation or test irrelevant cosmetic changes.
3. Run configured checks with `python3 .harness/runner.py check`. Read logs for failures and unexpected success. The runner records actual commands and exit codes; its own passing status only covers the configured assertions.
4. Use `python3 .harness/runner.py audit` to identify unrun, failed, stale, missing, and user-reported results. Changed source or task criteria require revalidation. Never relabel old evidence as current.
5. For a manual check, give the user precise input, action, and expected output. Wait for their explicit observation. Only then record it with `manual --id ID --status pass|fail --observed TEXT --user-confirmed`. Attribute it as user-reported, not independently verified. Never add the flag on the basis of an AI assumption or screenshot you did not receive.
6. Distinguish AI-executed tests, user-reviewed output, and user-operated UI. Leave unknowns unverified. Do not use GUI/browser automation where Computer Use is forbidden.
7. Generate `.harness/work/verification.md` using `report` only during the permitted work phase. If the report shows gaps, fix or accurately describe them. Map required content to the actual requested submission files.

Report actual evidence IDs and limits. Readiness is local and conditional on the configured checks; it is not a contest grade, an authenticity guarantee, or official submission. Never fabricate logs, timestamps, file paths, or verification claims.

For solver work, independently check assignment completeness, hard rules, objective accounting and input version. Exercise impossible input, time limits, stale input and fallback exhaustion when relevant. Distinguish lack of a feasible result from proven infeasibility. Use flow.py event verified only after current runner audit passes; process timing samples do not establish correctness or optimality.

## v3 coordination

Question ambiguous acceptance or contradictions even this late: use stakeholder-bridge, pause affected checks/publication and revalidate after resolution. Do not mark a guess as passing. Evidence snapshots include intake, model, contract and question semantics; edits invalidate old evidence. All workers must be done, blocking HR resolved, intake/contract current before finish readiness. Review nonblocking assumptions and unimplemented guarantees explicitly.
